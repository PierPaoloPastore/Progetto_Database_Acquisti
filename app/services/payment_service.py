"""
Servizi per la gestione dei pagamenti/scadenze (Payment).

Funzioni principali:
- list_overdue_payments_for_ui(reference_date=None)
- generate_payment_schedule(start_date, end_date)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.models import Payment, Invoice
from app.repositories import list_overdue_payments
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
