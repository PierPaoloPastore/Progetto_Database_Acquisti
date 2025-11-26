"""
Servizio di import delle fatture elettroniche XML (FatturaPA).

Funzione principale:
- run_import(folder: Optional[str] = None) -> dict
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from flask import current_app

from app.extensions import db
from app.models import Supplier, Invoice
from app.parsers.fatturapa_parser import (
    InvoiceDTO,
    FatturaPAParseError,
    parse_invoice_xml,
)

# Importiamo la funzione repository corretta per gestire il fornitore
# Assicurati che app/repositories/supplier_repo.py sia aggiornato come indicato nel passo precedente
from app.repositories.supplier_repo import get_or_create_supplier_from_dto

# Importiamo le altre funzioni repository necessarie
from app.repositories import (
    get_invoice_by_file_name,
    create_invoice,
    create_invoice_line,
    create_vat_summary,
    create_payment,
    create_import_log,
)


def run_import(folder: Optional[str] = None) -> Dict:
    """
    Esegue l'import delle fatture XML da una cartella.

    Gestisce transazioni per singolo file per evitare che un errore su un file
    blocchi l'intero batch.
    """
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
        
        # Variabile per tracciare invoice_id in caso di successo
        current_invoice_id = None

        # 1. Controllo preliminare duplicati (lettura veloce)
        # Non serve transazione qui, è una select semplice
        existing_invoice = get_invoice_by_file_name(file_name)
        if existing_invoice is not None:
            _log_skip(logger, file_name, existing_invoice.id, summary)
            continue

        # 2. Parsing XML
        try:
            invoice_dto = parse_invoice_xml(xml_path)
        except Exception as exc:
            _log_error_parsing(logger, file_name, exc, summary, str(import_folder))
            continue

        # 3. Transazione di Scrittura (DB)
        # Usiamo un blocco try/except per gestire commit e rollback manualmente
        # per isolare ogni file.
        try:
            # A. Recupera o Crea Fornitore
            # CRITICO: Questa funzione fa flush(), quindi 'supplier.id' sarà popolato.
            supplier = get_or_create_supplier_from_dto(invoice_dto.supplier)
            
            if supplier.id is None:
                # Caso limite teorico se il flush fallisce silenziosamente
                raise ValueError(f"ID fornitore nullo per {supplier.name}")

            # B. Creazione Fattura
            invoice = _create_invoice_from_dto(invoice_dto, supplier)
            
            # C. Creazione Dettagli (Righe, IVA, Pagamenti)
            _create_lines_from_dto(invoice, invoice_dto)
            _create_vat_summaries_from_dto(invoice, invoice_dto)
            _create_payments_from_dto(invoice, invoice_dto)

            # D. Log di successo nel DB (tabella import_logs)
            create_import_log(
                file_name=file_name,
                file_hash=invoice_dto.file_hash,
                import_source=str(import_folder),
                status="success",
                message="Import completato con successo",
                invoice_id=invoice.id,
            )
            
            # Flush per assicurarsi che invoice.id sia definitivo prima del commit finale
            db.session.flush()
            current_invoice_id = invoice.id

            # E. COMMIT DELLA TRANSAZIONE
            # Se arriviamo qui, tutto è andato bene per questo file.
            db.session.commit()

            # Aggiornamento summary e log su file (post-commit)
            _log_success(logger, file_name, current_invoice_id, supplier.id, summary)

        except Exception as exc:
            # F. ROLLBACK IN CASO DI ERRORE
            # Annulla fornitore (se nuovo), fattura e righe create in questo ciclo
            db.session.rollback()
            
            # Log dell'errore (DB + File)
            _log_error_db(logger, file_name, exc, summary, str(import_folder), invoice_dto)

    return summary


# =========================
#  Funzioni di supporto (private)
# =========================

def _create_invoice_from_dto(dto: InvoiceDTO, supplier: Supplier) -> Invoice:
    """Crea l'oggetto Invoice usando l'ID fornitore garantito."""
    invoice = create_invoice(
        supplier_id=supplier.id,  # Qui ora è sicuro che non sia None
        invoice_number=dto.invoice_number,
        invoice_series=dto.invoice_series,
        invoice_date=dto.invoice_date,
        registration_date=dto.registration_date,
        currency=dto.currency,
        total_taxable_amount=dto.total_taxable_amount,
        total_vat_amount=dto.total_vat_amount,
        total_gross_amount=dto.total_gross_amount,
        doc_status=dto.doc_status,
        payment_status=dto.payment_status,
        due_date=dto.due_date,
        file_name=dto.file_name or "",
        file_hash=dto.file_hash,
        import_source=None,
        notes_internal=None,
    )
    return invoice


def _create_lines_from_dto(invoice: Invoice, dto: InvoiceDTO) -> None:
    """Crea le righe fattura."""
    for line_dto in dto.lines:
        create_invoice_line(
            invoice_id=invoice.id,
            category_id=None,
            line_number=line_dto.line_number,
            description=line_dto.description or "",
            quantity=line_dto.quantity,
            unit_of_measure=line_dto.unit_of_measure,
            unit_price=line_dto.unit_price,
            discount_amount=line_dto.discount_amount,
            discount_percent=line_dto.discount_percent,
            taxable_amount=line_dto.taxable_amount,
            vat_rate=line_dto.vat_rate,
            vat_amount=line_dto.vat_amount,
            total_line_amount=line_dto.total_line_amount,
            sku_code=line_dto.sku_code,
            internal_code=line_dto.internal_code,
        )


def _create_vat_summaries_from_dto(invoice: Invoice, dto: InvoiceDTO) -> None:
    """Crea i riepiloghi IVA."""
    for vs_dto in dto.vat_summaries:
        create_vat_summary(
            invoice_id=invoice.id,
            vat_rate=vs_dto.vat_rate,
            taxable_amount=vs_dto.taxable_amount,
            vat_amount=vs_dto.vat_amount,
            nature=vs_dto.nature,
        )


def _create_payments_from_dto(invoice: Invoice, dto: InvoiceDTO) -> None:
    """Crea i pagamenti/scadenze."""
    for p_dto in dto.payments:
        create_payment(
            invoice_id=invoice.id,
            due_date=p_dto.due_date,
            expected_amount=p_dto.expected_amount,
            payment_terms=p_dto.payment_terms,
            payment_method=p_dto.payment_method,
            paid_date=None,
            paid_amount=None,
            status="unpaid",
            notes=None,
        )


# =========================
#  Logging Helpers
# =========================

def _log_skip(logger, file_name, invoice_id, summary):
    """Gestisce il log per i file saltati."""
    logger.info(
        "File XML già importato, salto.",
        extra={"component": "import_service", "file_name": file_name, "status": "skipped"}
    )
    # Aggiorna summary
    summary["skipped"] += 1
    summary["details"].append({
        "file_name": file_name, 
        "status": "skipped", 
        "message": "Già presente", 
        "invoice_id": invoice_id
    })
    
    # Opzionale: Creare un log DB anche per lo skip (fuori dalla transazione principale)
    try:
        create_import_log(file_name, None, None, "skipped", "File già presente", invoice_id)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _log_success(logger, file_name, invoice_id, supplier_id, summary):
    """Gestisce il log per i file importati con successo."""
    logger.info(
        "Import fattura completato.",
        extra={
            "component": "import_service", 
            "file_name": file_name, 
            "status": "success",
            "invoice_id": invoice_id,
            "supplier_id": supplier_id
        }
    )
    summary["imported"] += 1
    summary["details"].append({
        "file_name": file_name, 
        "status": "success", 
        "message": "Import completato", 
        "invoice_id": invoice_id
    })


def _log_error_parsing(logger, file_name, exc, summary, folder):
    """Gestisce il log per errori di parsing XML (prima del DB)."""
    logger.error(
        "Errore di parsing FatturaPA.",
        exc_info=True,
        extra={"component": "import_service", "file_name": file_name, "status": "error"}
    )
    
    # Tentativo di salvare l'errore nel DB in una transazione isolata
    try:
        create_import_log(file_name, None, folder, "error", str(exc), None)
        db.session.commit()
    except Exception:
        db.session.rollback()

    summary["errors"] += 1
    summary["details"].append({
        "file_name": file_name, 
        "status": "error", 
        "message": str(exc), 
        "invoice_id": None
    })


def _log_error_db(logger, file_name, exc, summary, folder, dto):
    """Gestisce il log per errori durante la transazione DB."""
    logger.error(
        "Errore durante import DB.",
        exc_info=True,
        extra={"component": "import_service", "file_name": file_name, "status": "error"}
    )
    
    # Tentativo di salvare l'errore nel DB in una NUOVA transazione isolata
    # (poiché quella precedente è stata rollbackata)
    try:
        file_hash = dto.file_hash if dto else None
        create_import_log(file_name, file_hash, folder, "error", f"Errore DB: {exc}", None)
        db.session.commit()
    except Exception as log_exc:
        # Se fallisce anche il log, stampiamo solo su console/file
        db.session.rollback()
        logger.critical(f"Impossibile scrivere log errore DB per {file_name}: {log_exc}")

    summary["errors"] += 1
    summary["details"].append({
        "file_name": file_name, 
        "status": "error", 
        "message": str(exc), 
        "invoice_id": None
    })