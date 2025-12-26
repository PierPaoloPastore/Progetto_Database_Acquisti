"""
Servizio di import delle fatture elettroniche XML (FatturaPA).
Aggiornato per usare l'architettura Document e UnitOfWork.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
import base64
import json
from typing import Dict, List, Optional
from datetime import date, datetime

from lxml import etree
from flask import current_app

from app.models import LegalEntity
from app.parsers.fatturapa_parser_v2 import (
    InvoiceDTO,
    parse_invoice_xml,
    P7MExtractionError,
    FatturaPASkipFile,
)
from app.repositories.import_log_repo import create_import_log
from app.services.unit_of_work import UnitOfWork
from app.services.logging import log_structured_event
from app.services import settings_service
from app.services.settings_service import get_attachments_storage_path
from werkzeug.utils import secure_filename


def run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> Dict:
    app = current_app._get_current_object()
    logger = app.logger
    validate_xsd = bool(app.config.get("FATTURAPA_VALIDATE_XSD_WARN", False))

    import_folder = Path(folder) if folder else Path(settings_service.get_xml_inbox_path())
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
    xml_files = _select_import_files(xml_files_set)

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

        file_hash = _compute_file_hash(xml_path)
        header_data = _extract_header_data(xml_path)
        current_legal_entity_id = legal_entity_id
        archive_year = _resolve_archive_year(invoice_dtos)

        try:
            stored_rel_path = _store_import_file(xml_path, archive_year)
        except Exception as exc:
            _log_error_storage(logger, file_name, exc, summary, str(import_folder))
            continue

        for idx, invoice_dto in enumerate(invoice_dtos, start=1):
            # Nomina univoca per body multipli
            base_name = invoice_dto.file_name or file_name
            if len(invoice_dtos) > 1:
                invoice_dto.file_name = f"{base_name}#body{idx}"
            else:
                invoice_dto.file_name = base_name
            if file_hash is not None and not invoice_dto.file_hash and len(invoice_dtos) == 1:
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
                    document.file_path = stored_rel_path

                    uow.commit()

                    _store_attachments(logger, document.id, invoice_dto)

                    _log_success(
                        logger,
                        invoice_dto.file_name,
                        document.id,
                        supplier_id,
                        summary,
                    )

        except Exception as exc:
            _log_error_db(logger, file_name, exc, summary)
            continue

        try:
            _archive_original_file(xml_path, archive_year, import_folder)
        except Exception as exc:
            _log_error_storage(logger, file_name, exc, summary, str(import_folder))

    log_structured_event(
        action="run_import_completed",
        folder=str(import_folder),
        total_files=summary["total_files"],
        imported=summary["imported"],
        skipped=summary["skipped"],
        errors=summary["errors"],
    )

    return summary


def _store_attachments(logger, document_id: int, invoice_dto: InvoiceDTO):
    attachments = getattr(invoice_dto, "attachments", None) or []
    if not attachments:
        return

    base_dir = Path(get_attachments_storage_path())
    doc_dir = base_dir / str(document_id)
    doc_dir.mkdir(parents=True, exist_ok=True)

    metadata = []
    for idx, att in enumerate(attachments, start=1):
        if not getattr(att, "data_base64", None):
            continue

        original_name = att.filename or f"allegato_{idx}"
        safe_name = secure_filename(original_name) or f"allegato_{idx}"
        stored_name = f"{idx:02d}_{safe_name}"
        if "." not in stored_name and att.format:
            stored_name = f"{stored_name}.{att.format.lower()}"

        try:
            data = base64.b64decode(att.data_base64, validate=False)
        except Exception as exc:
            logger.warning(
                "Allegato non decodificabile",
                extra={"document_id": document_id, "attachment": original_name, "error": str(exc)},
            )
            continue

        out_path = doc_dir / stored_name
        out_path.write_bytes(data)

        metadata.append(
            {
                "original_name": original_name,
                "stored_name": stored_name,
                "description": att.description,
                "format": att.format,
                "compression": att.compression,
                "encryption": att.encryption,
                "size_bytes": len(data),
            }
        )

    if metadata:
        meta_path = doc_dir / "attachments.json"
        meta_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2), encoding="utf-8")


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

def _log_error_storage(logger, file_name, exc, summary, folder):
    logger.error(
        "Errore salvataggio/archivio file import.",
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
            "message": f"Storage error: {exc}",
        }
    )
    create_import_log(
        file_name=file_name,
        import_source=folder,
        status="error",
        message=f"Storage error: {exc}",
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

def _resolve_archive_year(invoice_dtos: List[InvoiceDTO]) -> int:
    for dto in invoice_dtos:
        if dto.invoice_date:
            return dto.invoice_date.year
        if dto.registration_date:
            return dto.registration_date.year
    return date.today().year

def _store_import_file(xml_path: Path, year: int) -> str:
    base_dir = Path(settings_service.get_xml_storage_path())
    year_dir = base_dir / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    target_name = settings_service.ensure_unique_filename(str(year_dir), xml_path.name)
    dest_path = year_dir / target_name
    shutil.copy2(xml_path, dest_path)

    return os.path.join(str(year), target_name)

def _archive_original_file(xml_path: Path, year: int, import_folder: Path) -> None:
    archive_dir = Path(settings_service.get_xml_archive_path(year, base_path=str(import_folder)))
    target_name = settings_service.ensure_unique_filename(str(archive_dir), xml_path.name)
    dest_path = archive_dir / target_name
    shutil.move(str(xml_path), str(dest_path))


def _select_import_files(candidates: set[Path]) -> List[Path]:
    """
    Seleziona i file da importare:
    - ignora i metadati (nome contiene _metadato)
    - se esistono sia .xml che .p7m per lo stesso documento, preferisce .xml
    """
    def _is_metadata(name: str) -> bool:
        return "_metadato" in name.lower()

    def _base_key(path: Path) -> str:
        name = path.name.lower()
        if name.endswith(".xml.p7m"):
            return name[:-len(".xml.p7m")]
        if name.endswith(".p7m"):
            return name[:-len(".p7m")]
        if name.endswith(".xml"):
            return name[:-len(".xml")]
        return name

    by_key: dict[str, list[Path]] = {}
    for path in candidates:
        if _is_metadata(path.name):
            continue
        key = _base_key(path)
        by_key.setdefault(key, []).append(path)

    selected: List[Path] = []
    for paths in by_key.values():
        xmls = [p for p in paths if p.name.lower().endswith(".xml")]
        if xmls:
            selected.append(sorted(xmls)[0])
            continue
        selected.append(sorted(paths)[0])

    return sorted(selected)
