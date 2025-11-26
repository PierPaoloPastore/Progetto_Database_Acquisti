"""
Route per la gestione delle fatture (Invoice).

Comprende:
- elenco fatture con filtri base (GET /invoices/)
- dettaglio fattura (GET /invoices/<id>)
- aggiornamento stato documento/pagamento (POST /invoices/<id>/status)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from app.services import (
    search_invoices,
    get_invoice_detail,
    update_invoice_status,
)
from app.repositories import list_suppliers

invoices_bp = Blueprint("invoices", __name__)


def _parse_date(value: str) -> Optional[datetime.date]:
    """Parsa una data in formato YYYY-MM-DD, restituendo None se vuota/non valida."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_decimal(value: str) -> Optional[Decimal]:
    """Parsa un decimal, restituendo None se vuota/non valida."""
    if not value:
        return None
    try:
        return Decimal(value.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


@invoices_bp.route("/", methods=["GET"])
def list_view():
    """
    Pagina elenco fatture con filtri base via querystring:

    - date_from, date_to (YYYY-MM-DD)
    - supplier_id
    - payment_status
    - min_total, max_total
    """
    date_from = _parse_date(request.args.get("date_from", ""))
    date_to = _parse_date(request.args.get("date_to", ""))
    supplier_id = request.args.get("supplier_id")
    payment_status = request.args.get("payment_status") or None
    min_total = _parse_decimal(request.args.get("min_total", ""))
    max_total = _parse_decimal(request.args.get("max_total", ""))

    supplier_id_int: Optional[int] = None
    if supplier_id:
        try:
            supplier_id_int = int(supplier_id)
        except ValueError:
            supplier_id_int = None

    invoices = search_invoices(
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id_int,
        payment_status=payment_status,
        min_total=min_total,
        max_total=max_total,
        limit=300,
    )

    suppliers = list_suppliers(include_inactive=False)

    return render_template(
        "invoices/list.html",
        invoices=invoices,
        suppliers=suppliers,
        filters={
            "date_from": date_from,
            "date_to": date_to,
            "supplier_id": supplier_id_int,
            "payment_status": payment_status,
            "min_total": min_total,
            "max_total": max_total,
        },
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
    doc_status = request.form.get("doc_status") or None
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
