"""
Servizi per la gestione delle fatture (Invoice).

Funzioni principali:
- search_invoices(...)           -> lista per schermata elenco
- get_invoice_detail(invoice_id) -> dettaglio completo per schermata dettaglio
- update_invoice_status(...)     -> aggiornamento stati documento/pagamento
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.services.logging import log_structured_event
from app.models import Invoice
from app.repositories.invoice_repository import (
    list_invoices,
    filter_invoices_by_date_range,
    filter_invoices_by_supplier,
    filter_invoices_by_payment_status,
    search_invoices_by_filters,
    get_invoice_by_id,
)
from app.services.dto import InvoiceSearchFilters
from app.services.unit_of_work import UnitOfWork


def search_invoices(
    filters: InvoiceSearchFilters,
    limit: Optional[int] = 200,
) -> List[Invoice]:
    """
    Ricerca fatture per filtro, pensata per la UI di elenco.

    `filters` rappresenta tutti i filtri consentiti nella pagina elenco.

    Applica i filtri in questo ordine:
    - legal entity e anno contabile
    - fornitore
    - stato documento
    - stato pagamento
    - data
    - range importo totale lordo
    """
    date_from = filters.date_from
    date_to = filters.date_to
    supplier_id = filters.supplier_id
    payment_status = filters.payment_status
    doc_status = filters.doc_status
    physical_copy_status = filters.physical_copy_status
    legal_entity_id = filters.legal_entity_id
    year = filters.year
    min_total = filters.min_total
    max_total = filters.max_total

    # Se sono presenti filtri nuovi usiamo la query combinata completa
    if (
        legal_entity_id is not None
        or year is not None
        or min_total is not None
        or max_total is not None
        or doc_status is not None
        or physical_copy_status is not None
    ):
        return search_invoices_by_filters(
            date_from=date_from,
            date_to=date_to,
            supplier_id=supplier_id,
            payment_status=payment_status,
            doc_status=doc_status,
            physical_copy_status=physical_copy_status,
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

    doc_status accetta i valori:
    imported, pending_physical_copy, verified, rejected, archived.

    Usa un UnitOfWork per gestire commit/rollback.
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

    # Logging solo se l'operazione è andata a buon fine (commit riuscito)
    log_structured_event(
        "update_invoice_status",
        invoice_id=invoice.id,
        doc_status=invoice.doc_status,
        payment_status=invoice.payment_status,
    )

    return invoice


def mark_physical_copy_received(invoice_id: int) -> Optional[Invoice]:
    """Segna la copia cartacea come ricevuta e aggiorna lo stato documento.

    - physical_copy_status viene impostato a ``received``
    - physical_copy_received_at viene impostato all'orario corrente
    - se lo stato documento non è già ``verified`` viene aggiornato a ``verified``
    """
    invoice = get_invoice_by_id(invoice_id)
    if invoice is None:
        return None

    with UnitOfWork() as session:
        invoice.physical_copy_status = "received"
        invoice.physical_copy_received_at = datetime.utcnow()
        if invoice.doc_status == "imported":
            invoice.doc_status = "verified"

        session.add(invoice)

    log_structured_event(
        "mark_invoice_physical_copy_received",
        invoice_id=invoice.id,
        physical_copy_status=invoice.physical_copy_status,
        doc_status=invoice.doc_status,
    )

    return invoice


def _send_physical_copy_request_email(invoice: Invoice) -> None:
    """Placeholder per invio email/PEC al fornitore per la copia cartacea."""
    log_structured_event(
        "send_physical_copy_request_email_placeholder",
        invoice_id=invoice.id,
        supplier_id=invoice.supplier_id,
    )


def request_physical_copy(invoice_id: int) -> Optional[Invoice]:
    """Imposta lo stato della copia cartacea come richiesta e salva il timestamp."""
    invoice = get_invoice_by_id(invoice_id)
    if invoice is None:
        return None

    with UnitOfWork() as session:
        invoice.physical_copy_status = "requested"
        invoice.physical_copy_requested_at = datetime.utcnow()
        session.add(invoice)

    _send_physical_copy_request_email(invoice)

    log_structured_event(
        "request_invoice_physical_copy",
        invoice_id=invoice.id,
        physical_copy_status=invoice.physical_copy_status,
    )

    return invoice
