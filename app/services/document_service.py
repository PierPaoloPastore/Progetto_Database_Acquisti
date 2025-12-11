"""
Servizi per la gestione dei Documenti.

Funzioni principali:
- search_documents(...)           -> lista generica con filtri
- get_document_detail(id)         -> dettaglio completo
- update_document_status(...)     -> aggiornamento stati
- mark_physical_copy_received(...) -> salvataggio copia fisica
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.services.logging import log_structured_event
from app.models import Document
from app.repositories import document_repo
from app.services.dto import DocumentSearchFilters
from app.services.unit_of_work import UnitOfWork


def search_documents(
    filters: DocumentSearchFilters,
    limit: Optional[int] = 200,
    document_type: Optional[str] = None,
) -> List[Document]:
    """Ricerca documenti per filtro."""
    return document_repo.search_documents(
        document_type=document_type,
        date_from=filters.date_from,
        date_to=filters.date_to,
        supplier_id=filters.supplier_id,
        payment_status=filters.payment_status,
        doc_status=filters.doc_status,
        physical_copy_status=filters.physical_copy_status,
        legal_entity_id=filters.legal_entity_id,
        accounting_year=filters.year,
        min_total=filters.min_total,
        max_total=filters.max_total,
        limit=limit,
    )


def get_document_detail(document_id: int) -> Optional[Dict[str, Any]]:
    """Restituisce un dizionario con il dettaglio completo del documento."""
    document = document_repo.get_document_by_id(document_id)
    if document is None:
        return None

    return {
        "invoice": document,  # Legacy
        "document": document,
        "supplier": document.supplier,
        "lines": document.lines.order_by("line_number").all(),
        "vat_summaries": document.vat_summaries.order_by("vat_rate").all(),
        "payments": document.payments.order_by("due_date").all(),
        "notes": document.notes.order_by("created_at").all(),
    }


def update_document_status(
    document_id: int,
    doc_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    due_date: Optional[date] = None,
) -> Optional[Document]:
    """Aggiorna lo stato documento e/o la data di scadenza."""
    with UnitOfWork() as session:
        document = session.get(Document, document_id)
        if document is None:
            return None

        if doc_status is not None:
            document.doc_status = doc_status
        if due_date is not None:
            document.due_date = due_date
        
        session.add(document)

    log_structured_event(
        "update_document_status",
        document_id=document.id,
        doc_status=document.doc_status,
    )
    return document


def confirm_document(document_id: int) -> Optional[Document]:
    """Conferma un documento importato."""
    with UnitOfWork() as session:
        document = session.get(Document, document_id)
        if document is None:
            return None

        document.doc_status = "verified"
        document.updated_at = datetime.utcnow()
        session.add(document)

    log_structured_event("confirm_document", document_id=document.id)
    return document


def reject_document(document_id: int) -> Optional[Document]:
    """Scarta un documento importato."""
    with UnitOfWork() as session:
        document = session.get(Document, document_id)
        if document is None:
            return None

        document.doc_status = "rejected"
        document.updated_at = datetime.utcnow()
        session.add(document)

    log_structured_event("reject_document", document_id=document.id)
    return document


def list_documents_to_review(order: str = "desc", document_type: str = 'invoice') -> List[Document]:
    """Restituisce i documenti importati da rivedere."""
    return document_repo.list_imported_documents(document_type=document_type, order=order)


def list_documents_without_physical_copy(order: str = "desc") -> List[Document]:
    """Elenco dei documenti senza copia fisica."""
    return document_repo.list_invoices_without_physical_copy(order=order)


def get_next_document_to_review(order: str = "desc", document_type: str = 'invoice') -> Optional[Document]:
    """Restituisce il prossimo documento da rivedere."""
    return document_repo.get_next_imported_document(document_type=document_type, order=order)


def mark_physical_copy_received(
    document_id: int, *, file: Optional[FileStorage] = None
) -> Optional[Document]:
    """Segna la copia cartacea come ricevuta e salva il file."""
    
    # 1. Recupera documento (usiamo db.session per essere sicuri)
    document = db.session.get(Document, document_id)
    if document is None:
        return None

    stored_path: Optional[str] = None

    try:
        # 2. Salva file su disco (se presente)
        if file is not None:
            from app.services.scan_service import store_physical_copy
            stored_path = store_physical_copy(document, file)
            # Assegna il path al documento
            document.physical_copy_file_path = stored_path

        # 3. Aggiorna stati
        document.physical_copy_status = "received"
        document.physical_copy_received_at = datetime.utcnow()
        
        if document.doc_status == "imported":
            document.doc_status = "verified"

        # 4. Salva nel DB (Commit esplicito)
        db.session.add(document)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        raise e

    log_structured_event(
        "mark_physical_copy_received",
        document_id=document.id,
        path=stored_path
    )
    return document


def request_physical_copy(document_id: int) -> Optional[Document]:
    with UnitOfWork() as session:
        document = session.get(Document, document_id)
        if document is None:
            return None

        document.physical_copy_status = "requested"
        document.physical_copy_requested_at = datetime.utcnow()
        session.add(document)

    log_structured_event("request_physical_copy", document_id=document.id)
    return document


class DocumentService:
    """Metodi di supporto statici."""

    @staticmethod
    def get_next_invoice_to_review() -> Optional[Document]:
        return get_next_document_to_review(document_type='invoice', order='asc')

    @staticmethod
    def review_and_confirm(document_id: int, form_data: Dict[str, Any]) -> tuple[bool, str]:
        document = document_repo.get_document_by_id(document_id)
        if document is None:
            return False, "Documento non trovato"

        if "number" in form_data:
            document.document_number = str(form_data.get("number") or "")

        raw_date = form_data.get("date")
        if raw_date:
            if isinstance(raw_date, date):
                document.document_date = raw_date
            elif isinstance(raw_date, str):
                try:
                    document.document_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
                except ValueError:
                    return False, "Data non valida"

        raw_total = form_data.get("total_amount")
        if raw_total not in (None, ""):
            try:
                document.total_gross_amount = Decimal(str(raw_total))
            except (ArithmeticError, ValueError, TypeError):
                return False, "Importo non valido"

        document.doc_status = "verified"

        try:
            db.session.add(document)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            return False, f"Errore salvataggio: {exc}"

        return True, "Revisione completata"

    @staticmethod
    def get_document_by_id(doc_id: int) -> Optional[Document]:
        return document_repo.get_document_by_id(doc_id)