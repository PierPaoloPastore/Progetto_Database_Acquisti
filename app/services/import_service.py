"""
Servizio di import delle fatture elettroniche XML (FatturaPA).

Funzione principale:
- run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> dict
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flask import current_app

from app.extensions import db
from app.models import Invoice
from app.parsers.fatturapa_parser import InvoiceDTO, parse_invoice_xml
from app.repositories.import_log_repo import create_import_log
from app.repositories.invoice_repository import (
    create_invoice_with_details,
    find_existing_invoice,
)
from app.repositories.supplier_repo import get_or_create_supplier_from_dto


def run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> Dict:
    """
    Esegue l'import delle fatture XML da una cartella.

    Gestisce transazioni per singolo file per evitare che un errore su un file
    blocchi l'intero batch.
    """
    if legal_entity_id is None:
        raise ValueError(
            "legal_entity_id è obbligatorio per importare le fatture e assegnare l'intestatario"
        )

    app = current_app._get_current_object()
    logger = app.logger

    import_folder = Path(folder or app.config.get("IMPORT_XML_FOLDER"))
    if not import_folder.exists():
        import_folder.mkdir(parents=True, exist_ok=True)

    xml_files: List[Path] = sorted(import_folder.glob("*.xml"))

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
        except Exception as exc:
            _log_error_parsing(logger, file_name, exc, summary, str(import_folder))
            continue

        try:
            supplier = get_or_create_supplier_from_dto(invoice_dto.supplier)
            if supplier.id is None:
                raise ValueError(f"ID fornitore nullo per {supplier.name}")

            invoice, created = _create_invoice_tree(
                invoice_dto,
                supplier.id,
                legal_entity_id,
                str(import_folder),
            )

            if not created:
                _log_skip(logger, file_name, invoice.id, summary, reason="Duplicato per file_name/file_hash")
                _safe_log_import(
                    file_name=file_name,
                    status="skipped",
                    message="Fattura già presente (nome/hash)",
                    invoice_id=invoice.id,
                    folder=str(import_folder),
                    file_hash=invoice_dto.file_hash,
                )
                continue

            create_import_log(
                file_name=file_name,
                file_hash=invoice_dto.file_hash,
                import_source=str(import_folder),
                status="success",
                message="Import completato con successo",
                invoice_id=invoice.id,
            )

            db.session.commit()
            _log_success(logger, file_name, invoice.id, supplier.id, summary)

        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            _log_error_db(logger, file_name, exc, summary, str(import_folder), invoice_dto)

    return summary


def _create_invoice_tree(
    invoice_dto: InvoiceDTO, supplier_id: int, legal_entity_id: int, import_source: str
) -> Tuple[Invoice, bool]:
    """Wrapper per creare fattura + dettagli usando il repository centralizzato."""
    return create_invoice_with_details(
        invoice_dto=invoice_dto,
        supplier_id=supplier_id,
        legal_entity_id=legal_entity_id,
        import_source=import_source,
    )


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
        exc_info=True,
        extra={"component": "import_service", "file_name": file_name, "status": "error"},
    )

    try:
        _safe_log_import(
            file_name=file_name,
            status="error",
            message=str(exc),
            invoice_id=None,
            folder=folder,
        )
    except Exception:
        db.session.rollback()

    summary["errors"] += 1
    summary["details"].append(
        {
            "file_name": file_name,
            "status": "error",
            "message": str(exc),
            "invoice_id": None,
        }
    )


def _log_error_db(logger, file_name, exc, summary, folder, dto: Optional[InvoiceDTO]):
    """Gestisce il log per errori durante la transazione DB."""
    logger.error(
        "Errore durante import DB.",
        exc_info=True,
        extra={"component": "import_service", "file_name": file_name, "status": "error"},
    )

    try:
        _safe_log_import(
            file_name=file_name,
            status="error",
            message=str(exc),
            invoice_id=None,
            folder=folder,
            file_hash=dto.file_hash if dto else None,
        )
    except Exception:
        db.session.rollback()

    summary["errors"] += 1
    summary["details"].append(
        {
            "file_name": file_name,
            "status": "error",
            "message": str(exc),
            "invoice_id": None,
        }
    )


# =========================
#  Persistenza Log Import
# =========================


def _safe_log_import(
    *,
    file_name: str,
    status: str,
    message: str,
    invoice_id: Optional[int],
    folder: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> None:
    """Crea un record di import_log con gestione errori sicura."""
    create_import_log(
        file_name=file_name,
        file_hash=file_hash,
        import_source=folder,
        status=status,
        message=message,
        invoice_id=invoice_id,
    )
