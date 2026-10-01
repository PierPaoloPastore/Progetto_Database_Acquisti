"""
Servizio di import delle fatture elettroniche XML (FatturaPA).
Aggiornato per usare l'architettura Document e UnitOfWork.
"""

from __future__ import annotations

import csv
import os
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from datetime import date, datetime

from lxml import etree
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.models import LegalEntity
from app.parsers.fatturapa_parser_v2 import (
    InvoiceDTO,
    parse_invoice_xml,
)
from app.parsers.fatturapa_parser import _clean_xml_bytes, _extract_xml_from_p7m
from app.services import settings_service


_IMPORT_RUN_LOCK = threading.Lock()


def run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None, batch_id=None) -> Dict:
    app = current_app._get_current_object()
    logger = app.logger
    validate_xsd = bool(app.config.get("FATTURAPA_VALIDATE_XSD_WARN", False))

    import_folder = Path(folder) if folder else Path(settings_service.get_xml_storage_path())
    if not import_folder.exists():
        import_folder.mkdir(parents=True, exist_ok=True)

    xml_files_set = _collect_import_files(import_folder)
    xml_files = _select_import_files(xml_files_set)

    return _run_import_paths(
        xml_files=xml_files,
        import_source=str(import_folder),
        archive_base=import_folder,
        legal_entity_id=legal_entity_id,
        logger=logger,
        validate_xsd=validate_xsd, batch_id=batch_id,
    )

def run_import_files(files: Sequence[FileStorage], legal_entity_id: Optional[int] = None, batch_id=None) -> Dict:
    app = current_app._get_current_object()
    return _run_import_paths(
        xml_files=[f for f in files if f and f.filename], import_source="upload",
        archive_base=Path(settings_service.get_xml_storage_path()),
        legal_entity_id=legal_entity_id, logger=app.logger,
        validate_xsd=bool(app.config.get("FATTURAPA_VALIDATE_XSD_WARN", False)), batch_id=batch_id,
    )


def _run_import_paths(
    xml_files: List[Path],
    import_source: str,
    archive_base: Path,
    legal_entity_id: Optional[int],
    logger,
    validate_xsd: bool, batch_id=None,
) -> Dict:
    with _IMPORT_RUN_LOCK:
        return _run_import_paths_locked(
            xml_files=xml_files,
            import_source=import_source,
            archive_base=archive_base,
            legal_entity_id=legal_entity_id,
            logger=logger,
            validate_xsd=validate_xsd, batch_id=batch_id,
        )


def _run_import_paths_locked(
    xml_files: List[Path], import_source: str, archive_base: Path,
    legal_entity_id: Optional[int], logger, validate_xsd: bool, batch_id=None,
) -> Dict:
    from uuid import uuid4
    from app.services.import_recovery_service import import_file, summarize, recover_imports
    batch_id = batch_id or str(uuid4())
    recover_imports()
    payloads = [import_file(path, batch_id, import_source, archive_base, legal_entity_id)
                for path in xml_files]
    summary = summarize(payloads, batch_id)
    summary["folder"] = import_source
    try:
        report = _write_import_report(summary, import_source, logger)
    except Exception:
        report = None
    if report:
        summary["report_path"] = report
    elif summary["details"]:
        summary["warnings"] += 1
        summary["details"].append({"file_name": "-", "status": "warning", "stage": "report",
                                    "message": "CSV non disponibile; esiti conservati nel registro import"})
    return summary


def _normalize_tax_id(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    cleaned = re.sub(r"\s+", "", value).strip().upper()
    cleaned = re.sub(r"[^A-Z0-9]", "", cleaned)
    return cleaned or None


def _extract_header_data(xml_path: Path, *, logger=None) -> Dict:
    def _first(node, xpath: str):
        result = node.xpath(xpath)
        return result[0] if result else None

    def _get_text(node, xpath: str) -> Optional[str]:
        target = _first(node, xpath)
        if target is not None and target.text:
            value = target.text.strip()
            return value or None
        return None

    def _parse_xml_bytes(xml_bytes: bytes):
        try:
            parser = etree.XMLParser(recover=True)
            return etree.fromstring(xml_bytes, parser=parser)
        except etree.XMLSyntaxError as exc:
            if "not proper UTF-8" in str(exc):
                enc_attempts = [
                    ("cp1252", "strict", False),
                    ("latin-1", "strict", False),
                    ("cp1252", "replace", True),
                    ("latin-1", "replace", True),
                ]
                for enc, mode, use_recover in enc_attempts:
                    try:
                        text = xml_bytes.decode(enc, errors=mode)
                        utf8_bytes = _clean_xml_bytes(text.encode("utf-8", errors="strict"))
                        if use_recover:
                            parser_recover = etree.XMLParser(recover=True)
                            return etree.fromstring(utf8_bytes, parser=parser_recover)
                        return etree.fromstring(utf8_bytes)
                    except Exception:
                        continue
            raise

    header_data: Dict[str, Dict[str, Optional[str]]] = {}

    try:
        if xml_path.suffix.lower() in [".p7m"]:
            xml_content = _extract_xml_from_p7m(xml_path, logger=logger)
        else:
            xml_content = xml_path.read_bytes()
        xml_content = _clean_xml_bytes(xml_content)
        root = _parse_xml_bytes(xml_content)
    except Exception:
        return header_data

    cc_node = _first(root, ".//*[local-name()='CessionarioCommittente']")
    if cc_node is None:
        if logger:
            logger.warning(
                "CessionarioCommittente assente nell'XML",
                extra={"component": "import_service", "file": xml_path.name},
            )
        return header_data

    denominazione = _get_text(
        cc_node,
        "./*[local-name()='DatiAnagrafici']/*[local-name()='Anagrafica']/*[local-name()='Denominazione']",
    )
    nome = _get_text(
        cc_node,
        "./*[local-name()='DatiAnagrafici']/*[local-name()='Anagrafica']/*[local-name()='Nome']",
    )
    cognome = _get_text(
        cc_node,
        "./*[local-name()='DatiAnagrafici']/*[local-name()='Anagrafica']/*[local-name()='Cognome']",
    )
    if denominazione:
        name = denominazione
    elif nome or cognome:
        name = " ".join(filter(None, [nome, cognome])).strip()
    else:
        name = None

    vat_number = _get_text(
        cc_node,
        "./*[local-name()='DatiAnagrafici']/*[local-name()='IdFiscaleIVA']/*[local-name()='IdCodice']",
    )
    fiscal_code = _get_text(
        cc_node, "./*[local-name()='DatiAnagrafici']/*[local-name()='CodiceFiscale']"
    )
    indirizzo = _get_text(
        cc_node, "./*[local-name()='Sede']/*[local-name()='Indirizzo']"
    )
    numero_civico = _get_text(
        cc_node, "./*[local-name()='Sede']/*[local-name()='NumeroCivico']"
    )
    address = indirizzo
    if indirizzo and numero_civico:
        address = f"{indirizzo} {numero_civico}"
    city = _get_text(cc_node, "./*[local-name()='Sede']/*[local-name()='Comune']")
    country = _get_text(cc_node, "./*[local-name()='Sede']/*[local-name()='Nazione']")

    header_data["cessionario_committente"] = {
        "name": name,
        "vat_number": vat_number,
        "fiscal_code": fiscal_code,
        "address": address,
        "city": city,
        "country": country,
    }

    if logger:
        logger.info(
            "CessionarioCommittente estratto",
            extra={
                "component": "import_service",
                "source_file": xml_path.name,
                "cc_name": name,
                "vat_number": vat_number,
                "fiscal_code": fiscal_code,
                "vat_number_clean": _normalize_tax_id(vat_number),
                "fiscal_code_clean": _normalize_tax_id(fiscal_code),
            },
        )

    return header_data


def _get_or_create_legal_entity(header_data: Dict, session) -> LegalEntity:
    cessionario = (header_data or {}).get("cessionario_committente") or {}

    def _normalize_name(value: Optional[str]) -> str:
        if not value:
            return ""
        return re.sub(r"[^A-Za-z0-9]+", "", value).lower()

    name = (cessionario.get("name") or "").strip() or None
    vat_number = _normalize_tax_id(cessionario.get("vat_number"))
    fiscal_code = _normalize_tax_id(cessionario.get("fiscal_code"))
    effective_vat = vat_number or fiscal_code

    existing = None
    if fiscal_code:
        existing = session.query(LegalEntity).filter_by(fiscal_code=fiscal_code).first()
        if existing is None and vat_number:
            vat_match = session.query(LegalEntity).filter_by(vat_number=vat_number).first()
            if vat_match and (not vat_match.fiscal_code or vat_match.fiscal_code == vat_match.vat_number):
                existing = vat_match
    elif vat_number:
        existing = session.query(LegalEntity).filter_by(vat_number=vat_number).first()

    if existing:
        updated = False
        if name and _normalize_name(existing.name) != _normalize_name(name):
            existing.name = name
            updated = True
        if fiscal_code and not existing.fiscal_code:
            existing.fiscal_code = fiscal_code
            updated = True
        if vat_number and existing.vat_number != vat_number:
            if existing.vat_number == (existing.fiscal_code or ""):
                other = (
                    session.query(LegalEntity)
                    .filter(LegalEntity.vat_number == vat_number, LegalEntity.id != existing.id)
                    .first()
                )
                if other is None:
                    existing.vat_number = vat_number
                    updated = True
        if updated:
            session.flush()
        return existing

    legal_entity = LegalEntity(
        name=name or "Soggetto sconosciuto",
        vat_number=effective_vat,
        fiscal_code=fiscal_code,
        address=cessionario.get("address"),
        city=cessionario.get("city"),
        country=cessionario.get("country") or "IT",
        created_at=datetime.utcnow(),
    )
    session.add(legal_entity)
    session.flush()
    return legal_entity


def _write_import_report(summary: Dict, import_source: str, logger) -> Optional[str]:
    details = summary.get("details") or []
    if not details:
        return None

    try:
        base_dir = Path(__file__).resolve().parents[2]
        from app.services.import_recovery_service import diagnostic_root
        from uuid import uuid4
        report_dir = diagnostic_root() / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        source_label = "upload" if import_source == "upload" else "server"
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_name = f"import_report_{source_label}_{timestamp}_{secure_filename(summary.get('batch_id', 'batch'))}_{uuid4().hex}.csv"
        report_path = report_dir / report_name

        fieldnames = [
            "file_name", "status", "stage", "error_type", "message", "invoice_id",
            "document_number", "document_date", "supplier_name", "document_data_source",
            "duplicate_reason", "existing_file_name", "same_file_name",
            "existing_document_number", "existing_document_date", "legal_entity_name", "attempt_id", "batch_id",
        ]
        temporary = report_path.with_suffix(".csv.part")
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for detail in details:
                row = {key: detail.get(key) or "" for key in fieldnames}
                writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, report_path)

        try:
            return str(report_path.relative_to(base_dir))
        except ValueError:
            return str(report_path)
    except Exception as exc:
        if logger:
            logger.warning(
                "Impossibile scrivere report import",
                extra={"component": "import_service", "error": str(exc)},
            )
        return None


def _resolve_archive_year(invoice_dtos: List[InvoiceDTO]) -> int:
    for dto in invoice_dtos:
        if dto.invoice_date:
            return dto.invoice_date.year
        if dto.registration_date:
            return dto.registration_date.year
    return date.today().year

def _import_filename(xml_path, invoice_dtos=None):
    filename = xml_path.name
    if not invoice_dtos:
        return filename
    dto = invoice_dtos[0]
    invoice_date = dto.invoice_date or dto.registration_date
    date_label = invoice_date.isoformat() if invoice_date else "senza-data"
    supplier = secure_filename(dto.supplier.name or "")[:80] or "fornitore"
    number = secure_filename((dto.invoice_number or "").replace("/", "-"))[:60] or "senza-numero"
    suffix = ".xml.p7m" if filename.lower().endswith(".xml.p7m") else xml_path.suffix.lower()
    multi = "_multi" if len(invoice_dtos) > 1 else ""
    return f"{date_label}_{supplier}_{number}{multi}{suffix}"


def _select_import_files(candidates: Sequence[Path]) -> List[Path]:
    # Anche gli omonimi XML/P7M passano dai controlli sul contenuto.
    return sorted(candidates)


def _collect_import_files(import_folder: Path) -> List[Path]:
    # WindowsPath confronta senza case: un set perderebbe file su NAS case-sensitive.
    return [path.resolve() for path in import_folder.rglob("*")
            if path.is_file() and path.suffix.lower() in {".xml", ".p7m"}
            and not any(part.lower() in {"archivio", ".import-staging", ".import-diagnostics"}
                        for part in path.parts)]
