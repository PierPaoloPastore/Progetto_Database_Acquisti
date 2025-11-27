"""
Servizi per la gestione delle fatture (Invoice).

Funzioni principali:
- search_invoices(...)           -> lista per schermata elenco
- get_invoice_detail(invoice_id) -> dettaglio completo per schermata dettaglio
- update_invoice_status(...)     -> aggiornamento stati documento/pagamento
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.models import Invoice
from app.repositories import (
    list_invoices,
    filter_invoices_by_date_range,
    filter_invoices_by_supplier,
    filter_invoices_by_payment_status,
    search_invoices_by_filters,
    get_invoice_by_id,
)
from app.services.unit_of_work import UnitOfWork


def search_invoices(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    supplier_id: Optional[int] = None,
    payment_status: Optional[str] = None,
    legal_entity_id: Optional[int] = None,
    year: Optional[int] = None,
    min_total: Optional[Decimal] = None,
    max_total: Optional[Decimal] = None,
    limit: int = 200,
) -> List[Invoice]:
    """
    Ricerca fatture per filtro, pensata per la UI di elenco.

    Applica i filtri in questo ordine:
    - legal entity e anno contabile
    - fornitore
    - stato pagamento
    - data
    - range importo totale lordo
    """
    # Se sono presenti filtri nuovi usiamo la query combinata completa
    if legal_entity_id is not None or year is not None or min_total is not None or max_total is not None:
        return search_invoices_by_filters(
            date_from=date_from,
            date_to=date_to,
            supplier_id=supplier_id,
            payment_status=payment_status,
            legal_entity_id=legal_entity_id,
            accounting_year=year,
            min_total=min_total,
            max_total=max_total,
            limit=limit,
        )

    # Base: filtro per data/supplier/payment come prima logica
    if supplier_id is not None:
        invoices = filter_invoices_by_supplier(
            supplier_id=supplier_id,
            date_from=date_from,
            date_to=date_to,
        )
    elif payment_status is not None:
        invoices = filter_invoices_by_payment_status(
            payment_status=payment_status,
            date_from=date_from,
            date_to=date_to,
        )
    elif date_from is not None or date_to is not None:
        invoices = filter_invoices_by_date_range(
            date_from=date_from,
            date_to=date_to,
        )
    else:
        invoices = list_invoices(limit=limit)

    # Filtro ulteriore per importi (se richiesto)
    if min_total is not None or max_total is not None:
        filtered: List[Invoice] = []
        for inv in invoices:
            total = inv.total_gross_amount
            if total is None:
                continue
            if min_total is not None and total < min_total:
                continue
            if max_total is not None and total > max_total:
                continue
            filtered.append(inv)
        invoices = filtered

    # Eventuale limit finale (se non già applicato)
    if limit is not None and len(invoices) > limit:
        invoices = invoices[:limit]

    return invoices


def get_invoice_detail(invoice_id: int) -> Optional[Dict[str, Any]]:
    """
    Restituisce un dizionario con il dettaglio completo della fattura:

    {
      "invoice": Invoice,
      "supplier": Supplier,
      "lines": [InvoiceLine, ...],
      "vat_summaries": [VatSummary, ...],
      "payments": [Payment, ...],
      "notes": [Note, ...],
    }

    Restituisce None se la fattura non esiste.
    """
    invoice = get_invoice_by_id(invoice_id)
    if invoice is None:
        return None

    supplier = invoice.supplier
    lines = invoice.lines.order_by("line_number").all()
    vat_summaries = invoice.vat_summaries.order_by("vat_rate").all()
    payments = invoice.payments.order_by("due_date").all()
    notes = invoice.notes.order_by("created_at").all()

    return {
        "invoice": invoice,
        "supplier": supplier,
        "lines": lines,
        "vat_summaries": vat_summaries,
        "payments": payments,
        "notes": notes,
    }


def update_invoice_status(
    invoice_id: int,
    doc_status: Optional[str] = None,
    payment_status: Optional[str] = None,
    due_date: Optional[date] = None,
) -> Optional[Invoice]:
    """
    Aggiorna lo stato documento e/o lo stato pagamento e/o la data di scadenza
    di una fattura.

    Esegue il commit immediatamente.
    Restituisce la fattura aggiornata oppure None se non esiste.
    """
    invoice = get_invoice_by_id(invoice_id)
    if invoice is None:
        return None

    with UnitOfWork() as session:
        if doc_status is not None:
            invoice.doc_status = doc_status
        if payment_status is not None:
            invoice.payment_status = payment_status
        if due_date is not None:
            invoice.due_date = due_date

        session.add(invoice)
        return invoice
