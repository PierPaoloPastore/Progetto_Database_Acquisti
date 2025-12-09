"""
Servizio di import delle fatture elettroniche XML (FatturaPA).

Funzione principale:
- run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> dict

Supporta:
- File .xml nativi
- File .p7m (firme digitali PKCS#7)
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional

from datetime import datetime

from lxml import etree

from flask import current_app

from app.extensions import db
from app.models import Invoice, LegalEntity
from app.parsers.fatturapa_parser import InvoiceDTO, parse_invoice_xml, P7MExtractionError
from app.repositories.import_log_repo import create_import_log
from app.repositories.invoice_repo import (
    create_invoice_with_details,
    find_existing_invoice,
)
from app.repositories.supplier_repo import get_or_create_supplier_from_dto
from app.services.logging import log_structured_event


def run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> Dict:
    """
    Esegue l'import delle fatture XML/P7M da una cartella.

    Gestisce transazioni per singolo file per evitare che un errore su un file
    blocchi l'intero batch.
    
    Supporta:
    - File .xml
    - File .p7m (firma digitale)
    """
    app = current_app._get_current_object()
    logger = app.logger

    import_folder = Path(folder or app.config.get("IMPORT_XML_FOLDER"))
    if not import_folder.exists():
        import_folder.mkdir(parents=True, exist_ok=True)

    # Cerca sia .xml che .p7m
    xml_files: List[Path] = sorted(
        list(import_folder.glob("*.xml")) + 
        list(import_folder.glob("*.p7m")) +
        list(import_folder.glob("*.P7M"))
    )

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

        existing_invoice = find_existing_invoice(file_name=file_name)
        if existing_invoice is not None:
            _log_skip(logger, file_name, existing_invoice.id, summary, reason="File già importato (nome)")
            continue

        invoice_dto: Optional[InvoiceDTO] = None
        try:
            invoice_dto = parse_invoice_xml(xml_path)
            # Garantiamo che il nome file dell'XML importato sia sempre valorizzato
            if not invoice_dto.file_name:
                invoice_dto.file_name = file_name
            # Calcoliamo l'hash del file per deduplicazione
            if not invoice_dto.file_hash:
                invoice_dto.file_hash = _compute_file_hash(xml_path)
        except P7MExtractionError as exc:
            # Errore specifico per P7M
            _log_error_p7m(logger, file_name, exc, summary, str(import_folder))
            continue
        except Exception as exc:
            _log_error_parsing(logger, file_name, exc, summary, str(import_folder))
            continue

        # A questo punto abbiamo un DTO valido
        try:
            db.session.begin_nested()

            # Estrai header_data per legal_entity
            header_data = _extract_header_data(xml_path)
            
            # Se non specificato esplicitamente, cerca di recuperare dall'XML
            if legal_entity_id is None:
                legal_entity = _get_or_create_legal_entity(header_data)
                legal_entity_id = legal_entity.id

            supplier = get_or_create_supplier_from_dto(invoice_dto.supplier)
            supplier_id = supplier.id

            invoice = _create_invoice_and_details(
                invoice_dto=invoice_dto,
                supplier_id=supplier_id,
                legal_entity_id=legal_entity_id,
                import_source=str(import_folder),
            )

            db.session.commit()

            _log_success(
                logger,
                file_name,
                invoice.id,
                supplier_id,
                summary,
            )

        except Exception as exc:
            db.session.rollback()
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


def _create_invoice_and_details(
    invoice_dto: InvoiceDTO,
    supplier_id: int,
    legal_entity_id: int,
    import_source: str,
) -> Invoice:
    """
    Crea l'Invoice con tutte le relazioni collegate.
    """
    return create_invoice_with_details(
        invoice_dto=invoice_dto,
        supplier_id=supplier_id,
        legal_entity_id=legal_entity_id,
        import_source=import_source,
    )


def _extract_header_data(xml_path: Path) -> Dict:
    """
    Estrae i dati del cessionario/committente dall'XML.
    
    Supporta sia file XML che P7M.
    """

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
        # Gestione P7M
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
            # File XML normale
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


def _get_or_create_legal_entity(header_data: Dict) -> LegalEntity:
    """Recupera o crea la LegalEntity in base ai dati di cessionario/committente."""
    cessionario = (header_data or {}).get("cessionario_committente") or {}
    vat_number = cessionario.get("vat_number") or cessionario.get("fiscal_code")

    if not vat_number:
        raise ValueError("legal_entity_id è obbligatorio e non è stato trovato nell'XML")

    existing = None
    if cessionario.get("vat_number"):
        existing = LegalEntity.query.filter_by(vat_number=cessionario["vat_number"]).first()
    elif cessionario.get("fiscal_code"):
        existing = LegalEntity.query.filter_by(
            fiscal_code=cessionario["fiscal_code"]
        ).first()

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
    db.session.add(legal_entity)
    db.session.flush()

    return legal_entity


# =========================
#  Logging Helpers
# =========================


def _log_skip(logger, file_name, invoice_id, summary, reason: str = ""):
    """Gestisce il log per i file saltati."""
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
    """Gestisce il log per i file importati con successo."""
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
    """Gestisce il log per errori di parsing XML (prima del DB)."""
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
    """Gestisce il log per errori di estrazione P7M."""
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
    """Gestisce il log per errori DB (durante il commit)."""
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
    """Calcola l'hash SHA-256 del file per deduplicazione."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()