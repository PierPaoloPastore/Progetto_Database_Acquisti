"""
Servizio di import delle fatture elettroniche XML (FatturaPA).
Aggiornato per usare l'architettura Document e UnitOfWork.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from lxml import etree
from flask import current_app

from app.models import LegalEntity
from app.parsers.fatturapa_parser import InvoiceDTO, parse_invoice_xml, P7MExtractionError, FatturaPASkipFile
from app.repositories.import_log_repo import create_import_log
from app.services.unit_of_work import UnitOfWork
from app.services.logging import log_structured_event


def run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> Dict:
    app = current_app._get_current_object()
    logger = app.logger
    validate_xsd = bool(app.config.get("FATTURAPA_VALIDATE_XSD_WARN", False))

    import_folder = Path(folder or app.config.get("IMPORT_XML_FOLDER"))
    if not import_folder.exists():
        import_folder.mkdir(parents=True, exist_ok=True)

    xml_files_set = {
        p.resolve()
        for p in (
            list(import_folder.glob("*.xml"))
            + list(import_folder.glob("*.p7m"))
            + list(import_folder.glob("*.P7M"))
        )
    }
    xml_files: List[Path] = sorted(xml_files_set)

    summary = {
        "folder": str(import_folder),
        "total_files": len(xml_files),
        "processed": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "details": [],
    }

    for xml_path in xml_files:
        file_name = xml_path.name
        summary["processed"] += 1

        invoice_dtos: List[InvoiceDTO] = []
        try:
            invoice_dtos = parse_invoice_xml(xml_path, validate_xsd=validate_xsd, logger=logger)
        except FatturaPASkipFile as exc:
            _log_skip(logger, file_name, None, summary, reason=str(exc))
            continue
        except P7MExtractionError as exc:
            _log_error_p7m(logger, file_name, exc, summary, str(import_folder))
            continue
        except Exception as exc:
            _log_error_parsing(logger, file_name, exc, summary, str(import_folder))
            continue

        file_hash = _compute_file_hash(xml_path) if len(invoice_dtos) == 1 else None
        header_data = _extract_header_data(xml_path)
        current_legal_entity_id = legal_entity_id

        for idx, invoice_dto in enumerate(invoice_dtos, start=1):
            # Nomina univoca per body multipli
            base_name = invoice_dto.file_name or file_name
            if len(invoice_dtos) > 1:
                invoice_dto.file_name = f"{base_name}#body{idx}"
            else:
                invoice_dto.file_name = base_name
            if file_hash is not None and not invoice_dto.file_hash:
                invoice_dto.file_hash = file_hash

        try:
            # Transazione Principale di Scrittura
            for invoice_dto in invoice_dtos:
                with UnitOfWork() as uow:
                    # LegalEntity
                    if current_legal_entity_id is None:
                        legal_entity = _get_or_create_legal_entity(header_data, uow.session)
                        current_legal_entity_id = legal_entity.id
                        legal_entity_id = current_legal_entity_id

                    # Duplicati per file_name/hash
                    existing_doc = uow.documents.find_existing(
                        file_name=invoice_dto.file_name,
                        file_hash=getattr(invoice_dto, "file_hash", None),
                    )
                    if existing_doc:
                        _log_skip(logger, invoice_dto.file_name, existing_doc.id, summary, reason="Duplicato per file_name/file_hash")
                        continue

                    # Supplier
                    supplier = uow.suppliers.get_or_create_from_dto(invoice_dto.supplier)
                    supplier_id = supplier.id

                    # Document
                    document, created = uow.documents.create_from_fatturapa(
                        invoice_dto=invoice_dto,
                        supplier_id=supplier_id,
                        legal_entity_id=current_legal_entity_id,
                        import_source=str(import_folder),
                    )
                    
                    if not created:
                        _log_skip(logger, invoice_dto.file_name, document.id, summary, reason="Duplicato per file_name/file_hash")
                        continue

                    uow.commit()

                    _log_success(
                        logger,
                        invoice_dto.file_name,
                        document.id,
                        supplier_id,
                        summary,
                    )

        except Exception as exc:
            _log_error_db(logger, file_name, exc, summary)

    log_structured_event(
        action="run_import_completed",
        folder=str(import_folder),
        total_files=summary["total_files"],
        imported=summary["imported"],
        skipped=summary["skipped"],
        errors=summary["errors"],
    )

    return summary


def _extract_header_data(xml_path: Path) -> Dict:
    def _first(node, xpath: str):
        result = node.xpath(xpath)
        return result[0] if result else None

    def _get_text(node, xpath: str) -> Optional[str]:
        target = _first(node, xpath)
        if target is not None and target.text:
            value = target.text.strip()
            return value or None
        return None

    header_data: Dict[str, Dict[str, Optional[str]]] = {}

    try:
        if xml_path.suffix.lower() in ['.p7m']:
            from app.parsers.fatturapa_parser import _extract_xml_from_p7m
            import tempfile
            xml_content = _extract_xml_from_p7m(xml_path)
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
                tmp.write(xml_content)
                tmp_path = tmp.name
            try:
                tree = etree.parse(tmp_path)
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        else:
            tree = etree.parse(str(xml_path))
        
        root = tree.getroot()
    except Exception:
        return header_data

    cc_node = _first(root, ".//*[local-name()='CessionarioCommittente']")
    if cc_node is None:
        return header_data

    name = _get_text(cc_node, ".//*[local-name()='Denominazione']") or _get_text(
        cc_node, ".//*[local-name()='Nome']"
    )
    surname = _get_text(cc_node, ".//*[local-name()='Cognome']")
    if not name and surname:
        name = surname

    vat_number = _get_text(
        cc_node, ".//*[local-name()='IdFiscaleIVA']/*[local-name()='IdCodice']"
    )
    fiscal_code = _get_text(cc_node, ".//*[local-name()='CodiceFiscale']")
    address = _get_text(cc_node, ".//*[local-name()='Sede']/*[local-name()='Indirizzo']")
    city = _get_text(cc_node, ".//*[local-name()='Sede']/*[local-name()='Comune']")
    country = _get_text(cc_node, ".//*[local-name()='Sede']/*[local-name()='Nazione']")

    header_data["cessionario_committente"] = {
        "name": name,
        "vat_number": vat_number,
        "fiscal_code": fiscal_code,
        "address": address,
        "city": city,
        "country": country,
    }

    return header_data


def _get_or_create_legal_entity(header_data: Dict, session) -> LegalEntity:
    cessionario = (header_data or {}).get("cessionario_committente") or {}
    vat_number = cessionario.get("vat_number") or cessionario.get("fiscal_code")

    existing = None
    if cessionario.get("vat_number"):
        existing = session.query(LegalEntity).filter_by(vat_number=cessionario["vat_number"]).first()
    elif cessionario.get("fiscal_code"):
        existing = session.query(LegalEntity).filter_by(fiscal_code=cessionario["fiscal_code"]).first()

    if existing:
        return existing

    legal_entity = LegalEntity(
        name=cessionario.get("name") or "Soggetto sconosciuto",
        vat_number=vat_number,
        fiscal_code=cessionario.get("fiscal_code"),
        address=cessionario.get("address"),
        city=cessionario.get("city"),
        country=cessionario.get("country") or "IT",
        created_at=datetime.utcnow(),
    )
    session.add(legal_entity)
    session.flush()
    return legal_entity


def _log_skip(logger, file_name, invoice_id, summary, reason: str = ""):
    logger.info(
        "File XML già importato, salto.",
        extra={
            "component": "import_service",
            "file_name": file_name,
            "status": "skipped",
            "reason": reason or None,
        },
    )
    summary["skipped"] += 1
    summary["details"].append(
        {
            "file_name": file_name,
            "status": "skipped",
            "message": reason or "Già presente",
            "invoice_id": invoice_id,
        }
    )


def _log_success(logger, file_name, invoice_id, supplier_id, summary):
    logger.info(
        "Import fattura completato.",
        extra={
            "component": "import_service",
            "file_name": file_name,
            "status": "success",
            "invoice_id": invoice_id,
            "supplier_id": supplier_id,
        },
    )
    summary["imported"] += 1
    summary["details"].append(
        {
            "file_name": file_name,
            "status": "success",
            "message": "Import completato",
            "invoice_id": invoice_id,
        }
    )


def _log_error_parsing(logger, file_name, exc, summary, folder):
    logger.error(
        "Errore di parsing FatturaPA.",
        exc_info=exc,
        extra={
            "component": "import_service",
            "file_name": file_name,
            "status": "error",
        },
    )
    summary["errors"] += 1
    summary["details"].append(
        {
            "file_name": file_name,
            "status": "error",
            "message": f"Parsing error: {exc}",
        }
    )
    create_import_log(
        file_name=file_name,
        import_source=folder,
        status="error",
        message=f"Parsing error: {exc}",
    )


def _log_error_p7m(logger, file_name, exc, summary, folder):
    logger.error(
        "Errore estrazione XML da file P7M.",
        exc_info=exc,
        extra={
            "component": "import_service",
            "file_name": file_name,
            "status": "error",
        },
    )
    summary["errors"] += 1
    summary["details"].append(
        {
            "file_name": file_name,
            "status": "error",
            "message": f"Estrazione P7M fallita: {exc}",
        }
    )
    create_import_log(
        file_name=file_name,
        import_source=folder,
        status="error",
        message=f"P7M extraction error: {exc}",
    )


def _log_error_db(logger, file_name, exc, summary):
    logger.error(
        "Errore durante il commit.",
        exc_info=exc,
        extra={
            "component": "import_service",
            "file_name": file_name,
            "status": "error",
        },
    )
    summary["errors"] += 1
    summary["details"].append(
        {
            "file_name": file_name,
            "status": "error",
            "message": f"DB error: {exc}",
        }
    )


def _compute_file_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()
