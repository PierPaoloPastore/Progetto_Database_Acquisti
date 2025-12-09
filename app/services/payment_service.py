"""
Servizi per la gestione dei pagamenti/scadenze (Payment).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Document, Payment, PaymentDocument
from app.repositories import (
    create_payment,
    create_payment_document,
    get_payment_document,
    list_overdue_payments,
    list_payment_documents_by_status,
)
from app.services import scan_service, settings_service
from app.services.unit_of_work import UnitOfWork


def list_overdue_payments_for_ui(
    reference_date: Optional[date] = None,
) -> List[Dict[str, Any]]:
    """
    Restituisce i pagamenti scaduti e non pagati.
    """
    payments = list_overdue_payments(reference_date=reference_date)
    results: List[Dict[str, Any]] = []

    for p in payments:
        document: Document = p.document
        supplier_name = document.supplier.name if document and document.supplier else "N/A"
        results.append(
            {
                "payment": p,
                "invoice": document, # Chiave legacy 'invoice'
                "supplier_name": supplier_name,
            }
        )

    return results


def generate_payment_schedule(
    start_date: date,
    end_date: date,
) -> List[Dict[str, Any]]:
    """
    Genera uno scadenzario dei pagamenti tra start_date e end_date.
    """
    query = (
        Payment.query.filter(
            Payment.due_date.isnot(None),
            Payment.due_date >= start_date,
            Payment.due_date <= end_date,
        )
        .order_by(Payment.due_date.asc(), Payment.id.asc())
    )

    payments: List[Payment] = query.all()
    results: List[Dict[str, Any]] = []

    for p in payments:
        document: Document = p.document
        supplier_name = document.supplier.name if document and document.supplier else "N/A"
        results.append(
            {
                "payment": p,
                "invoice": document,
                "supplier_name": supplier_name,
            }
        )

    return results


def create_payment(
    invoice_id: int,
    due_date: Optional[date] = None,
    expected_amount: Optional[Any] = None,
    payment_terms: Optional[str] = None,
    payment_method: Optional[str] = None,
    paid_date: Optional[date] = None,
    paid_amount: Optional[Any] = None,
    status: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[Payment]:
    """Crea un nuovo pagamento associato a un documento."""

    with UnitOfWork() as session:
        document = session.get(Document, invoice_id)
        if document is None:
            return None

        payment = Payment(
            document_id=document.id,
            due_date=due_date,
            expected_amount=expected_amount,
            payment_terms=payment_terms,
            payment_method=payment_method,
            paid_date=paid_date,
            paid_amount=paid_amount,
            status=status or "unpaid",
            notes=notes,
        )
        session.add(payment)
        session.flush()

        return payment


def update_payment(
    payment_id: int,
    **kwargs: Any,
) -> Optional[Payment]:
    """Aggiorna i campi di un pagamento esistente."""

    with UnitOfWork() as session:
        payment = session.get(Payment, payment_id)
        if payment is None:
            return None

        for field, value in kwargs.items():
            if hasattr(payment, field):
                setattr(payment, field, value)

        session.flush()
        return payment


def _detect_payment_type(filename: str) -> str:
    """Euristica minimale sul tipo di pagamento in base al nome file."""
    lowered = (filename or "").lower()
    if "bonifico" in lowered: return "bonifico"
    if "mav" in lowered: return "mav"
    if "assegno" in lowered or "cheque" in lowered: return "assegno"
    return "sconosciuto"


def upload_payment_documents(files: List[FileStorage]) -> List[PaymentDocument]:
    """Carica e registra i PDF di pagamento."""
    stored_documents: List[PaymentDocument] = []
    base_path = settings_service.get_payment_files_storage_path()

    for file in files:
        if file is None or not file.filename:
            continue

        payment_type = _detect_payment_type(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        cleaned_original = secure_filename(file.filename)
        stored_name = f"payment_{timestamp}_{cleaned_original}" if cleaned_original else f"payment_{timestamp}.pdf"

        stored_path = scan_service.store_payment_document_file(
            file=file, base_path=base_path, filename=stored_name
        )

        with UnitOfWork() as session:
            document = create_payment_document(
                file_name=file.filename,
                file_path=stored_path,
                payment_type=payment_type,
                status="pending_review",
                uploaded_at=datetime.utcnow(),
            )
            session.flush()
            stored_documents.append(document)

    return stored_documents


def get_payment_inbox(statuses: List[str]) -> List[PaymentDocument]:
    return list_payment_documents_by_status(statuses)


def review_payment_document(document_id: int) -> Dict[str, Any]:
    """Carica il documento e i documenti candidati per l'associazione."""

    document = get_payment_document(document_id)
    if document is None:
        raise ValueError("Documento di pagamento non trovato")

    # Mostriamo gli ultimi 200 documenti (tipo invoice)
    candidate_invoices = (
        Document.query
        .filter_by(document_type='invoice')
        .order_by(Document.document_date.desc())
        .limit(200)
        .all()
    )

    return {"document": document, "candidate_invoices": candidate_invoices}


def assign_payments_to_invoices(
    document_id: int, assignments: List[Dict[str, Any]]
) -> PaymentDocument:
    """Crea pagamenti collegati al documento e aggiorna gli stati."""

    with UnitOfWork() as session:
        doc_payment: Optional[PaymentDocument] = session.get(PaymentDocument, document_id)
        if doc_payment is None:
            raise ValueError("Documento di pagamento non trovato")

        total_assigned = Decimal("0")

        for assignment in assignments:
            invoice_id = assignment.get("invoice_id")
            raw_amount = assignment.get("amount")
            if invoice_id is None or raw_amount in (None, ""):
                continue

            amount = Decimal(str(raw_amount))
            if amount <= 0:
                continue

            paid_date_raw = assignment.get("paid_date")
            paid_date = None
            if paid_date_raw:
                try:
                    paid_date = datetime.strptime(paid_date_raw, "%Y-%m-%d").date()
                except ValueError:
                    paid_date = None
            notes = assignment.get("notes")
            payment_method = assignment.get("payment_method")

            document: Optional[Document] = session.get(Document, invoice_id)
            if document is None:
                continue

            doc_gross = Decimal(document.total_gross_amount or 0)

            payment = create_payment(
                invoice=document, # create_payment accetta Document ma il param si chiama invoice in repo (da fixare se strict)
                amount=amount,
                payment_document=doc_payment,
                paid_date=paid_date,
                payment_method=payment_method or doc_payment.payment_type,
                status="paid" if doc_gross and amount >= doc_gross else "partial",
                notes=notes,
            )
            session.add(payment)
            total_assigned += amount

        if doc_payment.parsed_amount is not None and total_assigned < Decimal(doc_payment.parsed_amount):
            doc_payment.status = "partially_assigned"
        elif total_assigned > 0:
            doc_payment.status = "processed"
        else:
            doc_payment.status = "pending_review"

        session.flush()
        return doc_payment