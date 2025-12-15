"""
Service layer for payments and batch payment handling.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Sequence

from werkzeug.utils import secure_filename

from app.models import Payment, PaymentDocument
from app.services import scan_service, settings_service
from app.services.unit_of_work import UnitOfWork


def add_payment(amount, payment_date, description):
    """Create a single payment entry mapping payment_date -> due_date."""
    with UnitOfWork() as uow:
        payment = Payment(
            expected_amount=amount,
            due_date=payment_date,
            notes=description,
        )
        uow.payments.add(payment)
        uow.commit()
        return payment


def create_batch_payment(file, allocations: Sequence[dict], method: str | None, notes: str | None):
    """Create a batch payment document and allocate payments."""
    if not allocations:
        raise ValueError("No allocations provided for batch payment.")

    today = date.today()
    base_path = settings_service.get_payment_files_storage_path()

    if file:
        safe_name = secure_filename(getattr(file, "filename", "")) or f"batch_payment_{today.isoformat()}.pdf"
        relative_path = scan_service.store_payment_document_file(file=file, base_path=base_path, filename=safe_name)
        file_name = safe_name
        file_path = relative_path
    else:
        placeholder = f"batch_payment_{today.isoformat()}.pdf"
        file_name = placeholder
        file_path = placeholder

    with UnitOfWork() as uow:
        payment_document = PaymentDocument(
            file_name=file_name,
            file_path=file_path,
            payment_type=method or "batch",
            status="processed",
        )
        uow.session.add(payment_document)
        uow.session.flush()

        for allocation in allocations:
            payment_id = allocation.get("id")
            amount_value = allocation.get("amount")
            if payment_id is None or amount_value is None:
                continue

            payment = uow.payments.get_by_id(int(payment_id))
            if not payment:
                continue

            increment = Decimal(str(amount_value))
            current_paid = Decimal(payment.paid_amount or 0)
            payment.paid_amount = current_paid + increment
            payment.status = "PAID"
            payment.paid_date = today
            payment.payment_method = method
            payment.notes = notes
            payment.payment_document = payment_document

        uow.commit()
        return payment_document


def get_overdue_payments() -> List[Payment]:
    """Return payments with due_date in the past, ordered by due_date."""
    today = date.today()
    with UnitOfWork() as uow:
        return (
            uow.session.query(Payment)
            .filter(Payment.due_date != None, Payment.due_date <= today)  # noqa: E711
            .order_by(Payment.due_date.asc())
            .all()
        )


def get_all_unpaid_payments() -> List[Payment]:
    """Return all unpaid payments ordered by due_date."""
    with UnitOfWork() as uow:
        return (
            uow.session.query(Payment)
            .filter(Payment.status != "PAID")
            .order_by(Payment.due_date.asc())
            .all()
        )
