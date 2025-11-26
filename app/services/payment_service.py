"""
Servizi per la gestione dei pagamenti/scadenze (Payment).

Funzioni principali:
- list_overdue_payments_for_ui(reference_date=None)
- generate_payment_schedule(start_date, end_date)
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models import Payment, Invoice
from app.repositories import list_overdue_payments


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
