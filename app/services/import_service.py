"""
Servizio di import delle fatture elettroniche XML (FatturaPA).
Aggiornato per usare l'architettura Document e UnitOfWork.
"""

from __future__ import annotations

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
from app.repositories.import_log_repo import create_import_log
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

    xml_files_set = {
        p.resolve()
        for p in (
            list(import_folder.glob("*.xml"))
            + list(import_folder.glob("*.p7m"))
            + list(import_folder.glob("*.P7M"))
        )
    }
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
            _log_error_p7m(logger, file_name, exc, summary, import_source)
            continue
        except Exception as exc:
            _log_error_parsing(logger, file_name, exc, summary, import_source)
            continue

        file_hash = _compute_file_hash(xml_path)
        header_data = _extract_header_data(xml_path)
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
                        import_source=import_source,
                    )
                    
                    if not created:
                        _log_skip(logger, invoice_dto.file_name, document.id, summary, reason="Duplicato per file_name/file_hash")
                        continue
                    document.file_path = stored_rel_path

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

    log_structured_event(
        action="run_import_completed",
        folder=import_source,
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
            xml_content = _extract_xml_from_p7m(xml_path)
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
