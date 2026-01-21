"""
Servizio di import delle fatture elettroniche XML (FatturaPA).
Aggiornato per usare l'architettura Document e UnitOfWork.
"""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence
from datetime import date, datetime

from lxml import etree
from flask import current_app
from werkzeug.datastructures import FileStorage

from app.models import LegalEntity
from app.parsers.fatturapa_parser_v2 import (
    InvoiceDTO,
    parse_invoice_xml,
    P7MExtractionError,
    FatturaPASkipFile,
)
from app.parsers.fatturapa_parser import _clean_xml_bytes, _extract_xml_from_p7m
from app.repositories.import_log_repo import create_import_log, find_document_by_file_hash
from app.services.unit_of_work import UnitOfWork
from app.services.logging import log_structured_event
from app.services import settings_service


def run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> Dict:
    app = current_app._get_current_object()
    logger = app.logger
    validate_xsd = bool(app.config.get("FATTURAPA_VALIDATE_XSD_WARN", False))

    import_folder = Path(folder) if folder else Path(settings_service.get_xml_inbox_path())
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
        validate_xsd=validate_xsd,
    )

def run_import_files(files: Sequence[FileStorage], legal_entity_id: Optional[int] = None) -> Dict:
    app = current_app._get_current_object()
    logger = app.logger
    validate_xsd = bool(app.config.get("FATTURAPA_VALIDATE_XSD_WARN", False))

    archive_base = Path(settings_service.get_xml_inbox_path())
    if not archive_base.exists():
        archive_base.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        xml_files_set: set[Path] = set()

        for storage in files:
            if not storage or not storage.filename:
                continue
            file_name = Path(storage.filename).name
            if not file_name:
                continue
            lower_name = file_name.lower()
            if not (lower_name.endswith(".xml") or lower_name.endswith(".p7m")):
                continue
            safe_name = settings_service.ensure_unique_filename(str(temp_root), file_name)
            dest_path = temp_root / safe_name
            storage.save(str(dest_path))
            xml_files_set.add(dest_path.resolve())

        xml_files = _select_import_files(xml_files_set)
        return _run_import_paths(
            xml_files=xml_files,
            import_source="upload",
            archive_base=archive_base,
            legal_entity_id=legal_entity_id,
            logger=logger,
            validate_xsd=validate_xsd,
        )


def _run_import_paths(
    xml_files: List[Path],
    import_source: str,
    archive_base: Path,
    legal_entity_id: Optional[int],
    logger,
    validate_xsd: bool,
) -> Dict:
    summary = {
        "folder": import_source,
        "total_files": len(xml_files),
        "processed": 0,
        "imported": 0,
        "skipped": 0,
        "warnings": 0,
        "errors": 0,
        "details": [],
    }

    if not xml_files:
        _log_error_scan(logger, import_source, summary)

    for xml_path in xml_files:
        file_name = xml_path.name
        summary["processed"] += 1

        with UnitOfWork() as uow:
            existing_doc = uow.documents.find_existing_by_file_base(file_name)
        if existing_doc:
            _log_skip(
                logger,
                file_name,
                existing_doc.id,
                summary,
                reason="Duplicato per file_name (pre-parse)",
                stage="precheck",
            )
            continue

        file_hash = _compute_file_hash(xml_path)
        existing_by_hash = find_document_by_file_hash(file_hash)
        if existing_by_hash:
            _log_skip(
                logger,
                file_name,
                existing_by_hash,
                summary,
                reason="Duplicato per file_hash (pre-parse)",
                stage="precheck",
            )
            continue

        invoice_dtos: List[InvoiceDTO] = []
        try:
            invoice_dtos = parse_invoice_xml(xml_path, validate_xsd=validate_xsd, logger=logger)
        except FatturaPASkipFile as exc:
            _log_skip(logger, file_name, None, summary, reason=str(exc), stage="skip")
            continue
        except P7MExtractionError as exc:
            _log_error_p7m(logger, file_name, exc, summary, import_source)
            continue
        except Exception as exc:
            warning_doc_id = _handle_parsing_warning(
                xml_path=xml_path,
                file_name=file_name,
                file_hash=file_hash,
                import_source=import_source,
                archive_base=archive_base,
                logger=logger,
                error=exc,
            )
            if warning_doc_id:
                _log_warning_parsing(
                    logger,
                    file_name,
                    exc,
                    summary,
                    import_source,
                    warning_doc_id,
                )
            else:
                _log_error_parsing(logger, file_name, exc, summary, import_source)
            continue

        header_data = _extract_header_data(xml_path, logger=logger)
        current_legal_entity_id = legal_entity_id
        archive_year = _resolve_archive_year(invoice_dtos)

        try:
            stored_rel_path = _store_import_file(xml_path, archive_year)
        except Exception as exc:
            _log_error_storage(logger, file_name, exc, summary, import_source)
            continue

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
                        _log_skip(
                            logger,
                            invoice_dto.file_name,
                            existing_doc.id,
                            summary,
                            reason="Duplicato per file_name/file_hash",
                            stage="postcheck",
                        )
                        continue

                    # Supplier
                    supplier = uow.suppliers.get_or_create_from_dto(invoice_dto.supplier)
                    supplier_id = supplier.id

                    # Document
                    document, created = uow.documents.create_from_fatturapa(
                        invoice_dto=invoice_dto,
                        supplier_id=supplier_id,
                        legal_entity_id=current_legal_entity_id,
                        import_source=import_source,
                    )
                    
                    if not created:
                        _log_skip(
                            logger,
                            invoice_dto.file_name,
                            document.id,
                            summary,
                            reason="Duplicato per file_name/file_hash",
                            stage="postcheck",
                        )
                        continue
                    document.file_path = stored_rel_path
                    create_import_log(
                        file_name=invoice_dto.file_name,
                        file_hash=invoice_dto.file_hash,
                        import_source=import_source,
                        status="success",
                        message="Import completato",
                        document_id=document.id,
                    )

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
            continue

        try:
            _archive_original_file(xml_path, archive_year, archive_base)
        except Exception as exc:
            _log_error_storage(logger, file_name, exc, summary, import_source)

    report_path = _write_import_report(summary, import_source, logger)
    if report_path:
        summary["report_path"] = report_path

    log_structured_event(
        action="run_import_completed",
        folder=import_source,
        total_files=summary["total_files"],
        imported=summary["imported"],
        skipped=summary["skipped"],
        warnings=summary["warnings"],
        errors=summary["errors"],
    )

    return summary


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


def _log_skip(logger, file_name, invoice_id, summary, reason: str = "", stage: str = "skip"):
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
            "stage": stage,
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
            "stage": "import",
            "message": "Import completato",
            "invoice_id": invoice_id,
        }
    )


def _log_warning_parsing(logger, file_name, exc, summary, folder, document_id: Optional[int]):
    logger.warning(
        "Parsing incompleto, documento creato in revisione.",
        exc_info=exc,
        extra={
            "component": "import_service",
            "file_name": file_name,
            "status": "warning",
        },
    )
    summary["warnings"] += 1
    summary["details"].append(
        {
            "file_name": file_name,
            "status": "warning",
            "stage": "parsing",
            "error_type": exc.__class__.__name__,
            "message": f"Parsing incompleto: {exc}",
            "invoice_id": document_id,
        }
    )


def _build_import_warning_note(exc: Exception) -> str:
    message = f"IMPORT_WARNING: parsing error: {exc}"
    if len(message) > 500:
        message = message[:497] + "..."
    return message


def _resolve_archive_year_from_path(xml_path: Path) -> int:
    try:
        return datetime.fromtimestamp(xml_path.stat().st_mtime).year
    except Exception:
        return date.today().year


def _handle_parsing_warning(
    *,
    xml_path: Path,
    file_name: str,
    file_hash: str,
    import_source: str,
    archive_base: Path,
    logger,
    error: Exception,
) -> Optional[int]:
    header_data = _extract_header_data(xml_path, logger=logger)
    archive_year = _resolve_archive_year_from_path(xml_path)
    stored_rel_path: Optional[str] = None
    try:
        stored_rel_path = _store_import_file(xml_path, archive_year)
    except Exception as exc:
        if logger:
            logger.warning(
                "Errore salvataggio file per import incompleto.",
                extra={
                    "component": "import_service",
                    "file_name": file_name,
                    "error": str(exc),
                },
            )
    import_source_for_doc = import_source
    if stored_rel_path is None:
        import_source_for_doc = str(xml_path)

    try:
        with UnitOfWork() as uow:
            legal_entity_id = None
            if header_data:
                legal_entity = _get_or_create_legal_entity(header_data, uow.session)
                legal_entity_id = legal_entity.id
            note = _build_import_warning_note(error)
            doc = uow.documents.create_import_placeholder(
                file_name=file_name,
                file_hash=file_hash,
                file_path=stored_rel_path,
                import_source=import_source_for_doc,
                legal_entity_id=legal_entity_id,
                note=note,
            )
            create_import_log(
                file_name=file_name,
                file_hash=file_hash,
                import_source=import_source,
                status="warning",
                message=note,
                document_id=doc.id,
            )
            uow.commit()
            document_id = doc.id
    except Exception as exc:
        if logger:
            logger.error(
                "Impossibile creare documento per parsing incompleto.",
                exc_info=exc,
                extra={
                    "component": "import_service",
                    "file_name": file_name,
                    "status": "error",
                },
            )
        return None

    if stored_rel_path:
        try:
            _archive_original_file(xml_path, archive_year, archive_base)
        except Exception as exc:
            if logger:
                logger.warning(
                    "Errore archiviazione file per import incompleto.",
                    extra={
                        "component": "import_service",
                        "file_name": file_name,
                        "error": str(exc),
                    },
                )

    return document_id


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
            "stage": "parsing",
            "error_type": exc.__class__.__name__,
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
            "stage": "storage",
            "error_type": exc.__class__.__name__,
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
            "stage": "p7m_extract",
            "error_type": exc.__class__.__name__,
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
            "stage": "db_commit",
            "error_type": exc.__class__.__name__,
            "message": f"DB error: {exc}",
        }
    )

def _log_error_scan(logger, import_source: str, summary):
    logger.warning(
        "Nessun file XML/P7M trovato nella cartella di import.",
        extra={
            "component": "import_service",
            "status": "error",
            "import_source": import_source,
        },
    )
    summary["errors"] += 1
    summary["details"].append(
        {
            "file_name": "-",
            "status": "error",
            "stage": "scan",
            "error_type": "FileNotFound",
            "message": f"Nessun file XML/P7M trovato nella cartella: {import_source}",
        }
    )


def _write_import_report(summary: Dict, import_source: str, logger) -> Optional[str]:
    details = summary.get("details") or []
    if not details:
        return None

    try:
        base_dir = Path(__file__).resolve().parents[2]
        report_dir = base_dir / "import_debug" / "import_reports"
        report_dir.mkdir(parents=True, exist_ok=True)

        source_label = "upload" if import_source == "upload" else "server"
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        report_name = f"import_report_{source_label}_{timestamp}.csv"
        report_path = report_dir / report_name

        fieldnames = ["file_name", "status", "stage", "error_type", "message", "invoice_id"]
        with report_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for detail in details:
                row = {key: detail.get(key) or "" for key in fieldnames}
                writer.writerow(row)

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

def _archive_original_file(xml_path: Path, year: int, archive_base: Path) -> None:
    archive_dir = Path(settings_service.get_xml_archive_path(year, base_path=str(archive_base)))
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


def _collect_import_files(import_folder: Path) -> set[Path]:
    def _is_archived(path: Path) -> bool:
        return any(part.lower() == "archivio" for part in path.parts)

    patterns = ("*.xml", "*.p7m", "*.P7M")
    found: set[Path] = set()
    for pattern in patterns:
        for path in import_folder.rglob(pattern):
            if _is_archived(path):
                continue
            found.add(path.resolve())
    return found
