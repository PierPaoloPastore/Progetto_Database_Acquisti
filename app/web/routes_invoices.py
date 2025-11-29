"""
Route per la gestione delle fatture (Invoice).

Comprende:
- elenco fatture con filtri base (GET /invoices/)
- dettaglio fattura (GET /invoices/<id>)
- aggiornamento stato documento/pagamento (POST /invoices/<id>/status)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from app.services import search_invoices, get_invoice_detail, update_invoice_status
from app.services.dto import InvoiceSearchFilters
from app.repositories import (
    list_suppliers,
    list_legal_entities,
    list_accounting_years,
)

invoices_bp = Blueprint("invoices", __name__)


def _parse_date(value: str) -> Optional[datetime.date]:
    """Parsa una data in formato YYYY-MM-DD, restituendo None se vuota/non valida."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
@invoices_bp.route("/", methods=["GET"])
def list_view():
    """
    Pagina elenco fatture con filtri base via querystring:

    - date_from, date_to (YYYY-MM-DD)
    - supplier_id
    - legal_entity_id
    - year (accounting_year)
    - doc_status
    - payment_status
    - min_total, max_total
    """
    filters = InvoiceSearchFilters.from_query_args(request.args)

    invoices = search_invoices(filters=filters, limit=300)

    suppliers = list_suppliers(include_inactive=False)
    legal_entities = list_legal_entities(include_inactive=False)
    accounting_years = list_accounting_years()

    return render_template(
        "invoices/list.html",
        invoices=invoices,
        suppliers=suppliers,
        legal_entities=legal_entities,
        accounting_years=accounting_years,
        filters=filters,
    )


@invoices_bp.route("/to-review", methods=["GET"])
def to_review_view():
    """Elenco fatture importate da rivedere (doc_status=imported di default)."""
    filters = InvoiceSearchFilters.from_query_args(request.args)

    if filters.doc_status is None:
        filters.doc_status = "imported"

    invoices = search_invoices(filters=filters, limit=300)

    suppliers = list_suppliers(include_inactive=False)
    legal_entities = list_legal_entities(include_inactive=False)
    accounting_years = list_accounting_years()

    return render_template(
        "invoices/list.html",
        invoices=invoices,
        suppliers=suppliers,
        legal_entities=legal_entities,
        accounting_years=accounting_years,
        filters=filters,
    )


@invoices_bp.route("/<int:invoice_id>", methods=["GET"])
def detail_view(invoice_id: int):
    """
    Pagina dettaglio fattura:

    Mostra:
    - dati testata
    - fornitore
    - righe fattura
    - riepilogo IVA
    - pagamenti
    - note
    """
    detail = get_invoice_detail(invoice_id)
    if detail is None:
        flash("Fattura non trovata.", "warning")
        return redirect(url_for("invoices.list_view"))

    return render_template(
        "invoices/detail.html",
        **detail,
    )


@invoices_bp.route("/<int:invoice_id>/status", methods=["POST"])
def update_status_view(invoice_id: int):
    """
    Aggiorna lo stato documento e/o lo stato pagamento di una fattura.

    Accetta form fields:
    - doc_status
    - payment_status
    - due_date (opzionale)
    """
    allowed_doc_statuses = {"imported", "verified", "rejected", "archived"}

    doc_status = request.form.get("doc_status") or None
    if doc_status is not None and doc_status not in allowed_doc_statuses:
        flash("Valore di stato documento non valido.", "danger")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))
    payment_status = request.form.get("payment_status") or None
    due_date_str = request.form.get("due_date") or ""
    due_date = _parse_date(due_date_str)

    invoice = update_invoice_status(
        invoice_id=invoice_id,
        doc_status=doc_status,
        payment_status=payment_status,
        due_date=due_date,
    )

    if invoice is None:
        flash("Fattura non trovata o errore di aggiornamento.", "danger")
    else:
        flash("Stato fattura aggiornato con successo.", "success")

    return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))
