"""
Servizi per la gestione dei pagamenti/scadenze (Payment).

Funzioni principali:
- list_overdue_payments_for_ui(reference_date=None)
- generate_payment_schedule(start_date, end_date)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Invoice, Payment, PaymentDocument
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
    Restituisce i pagamenti scaduti e non pagati alla data indicata,
    pronti per essere mostrati in una tabella UI.

    Output tipo:
    [
      {
        "payment": Payment,
        "invoice": Invoice,
        "supplier_name": str,
      },
      ...
    ]
    """
    payments = list_overdue_payments(reference_date=reference_date)
    results: List[Dict[str, Any]] = []

    for p in payments:
        invoice: Invoice = p.invoice
        supplier_name = invoice.supplier.name if invoice and invoice.supplier else "N/A"
        results.append(
            {
                "payment": p,
                "invoice": invoice,
                "supplier_name": supplier_name,
            }
        )

    return results


def generate_payment_schedule(
    start_date: date,
    end_date: date,
) -> List[Dict[str, Any]]:
    """
    Genera uno scadenzario dei pagamenti tra start_date e end_date (inclusi).

    Restituisce una lista di dict:
    [
      {
        "payment": Payment,
        "invoice": Invoice,
        "supplier_name": str,
      },
      ...
    ]
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
        invoice: Invoice = p.invoice
        supplier_name = invoice.supplier.name if invoice and invoice.supplier else "N/A"
        results.append(
            {
                "payment": p,
                "invoice": invoice,
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
    """Crea un nuovo pagamento associato a una fattura."""

    with UnitOfWork() as session:
        invoice = session.get(Invoice, invoice_id)
        if invoice is None:
            return None

        payment = Payment(
            invoice_id=invoice.id,
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
    if "bonifico" in lowered:
        return "bonifico"
    if "mav" in lowered:
        return "mav"
    if "assegno" in lowered or "cheque" in lowered:
        return "assegno"
    return "sconosciuto"


def upload_payment_documents(files: List[FileStorage]) -> List[PaymentDocument]:
    """Carica e registra i PDF di pagamento marcandoli come pending_review."""

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
    """Ritorna i documenti di pagamento filtrati per stato per la inbox."""

    return list_payment_documents_by_status(statuses)


def review_payment_document(document_id: int) -> Dict[str, Any]:
    """Carica il documento e le fatture candidate per l'associazione."""

    document = get_payment_document(document_id)
    if document is None:
        raise ValueError("Documento di pagamento non trovato")

    candidate_invoices = (
        Invoice.query.filter(Invoice.payment_status != "paid")
        .order_by(Invoice.invoice_date.desc())
        .limit(200)
        .all()
    )

    return {"document": document, "candidate_invoices": candidate_invoices}


def assign_payments_to_invoices(
    document_id: int, assignments: List[Dict[str, Any]]
) -> PaymentDocument:
    """Crea pagamenti collegati al documento e aggiorna gli stati fatture."""

    with UnitOfWork() as session:
        document: Optional[PaymentDocument] = session.get(PaymentDocument, document_id)
        if document is None:
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

            invoice: Optional[Invoice] = session.get(Invoice, invoice_id)
            if invoice is None:
                continue

            invoice_gross = Decimal(invoice.total_gross_amount or 0)

            payment = create_payment(
                invoice=invoice,
                amount=amount,
                payment_document=document,
                paid_date=paid_date,
                payment_method=payment_method or document.payment_type,
                status="paid" if invoice_gross and amount >= invoice_gross else "partial",
                notes=notes,
            )
            session.add(payment)
            total_assigned += amount

            update_invoice_payment_status(invoice.id, session=session)

        if document.parsed_amount is not None and total_assigned < Decimal(document.parsed_amount):
            document.status = "partially_assigned"
        elif total_assigned > 0:
            document.status = "processed"
        else:
            document.status = "pending_review"

        session.flush()
        return document


def update_invoice_payment_status(invoice_id: int, session=None) -> Optional[Invoice]:
    """Aggiorna il campo payment_status in base ai pagamenti registrati."""

    manage_context = session is None
    if manage_context:
        with UnitOfWork() as managed_session:
            return update_invoice_payment_status(invoice_id, session=managed_session)

    invoice: Optional[Invoice] = session.get(Invoice, invoice_id)
    if invoice is None:
        return None

    total_paid = (
        session.query(db.func.coalesce(db.func.sum(Payment.paid_amount), 0))
        .filter(Payment.invoice_id == invoice_id)
        .scalar()
    )

    gross_amount = invoice.total_gross_amount or Decimal("0")
    total_paid_decimal = Decimal(total_paid or 0)

    if total_paid_decimal == 0:
        invoice.payment_status = "unpaid"
    elif gross_amount and total_paid_decimal < gross_amount:
        invoice.payment_status = "partial"
    elif gross_amount and total_paid_decimal >= gross_amount:
        invoice.payment_status = "paid"
    else:
        invoice.payment_status = "partial"

    session.flush()
    return invoice
