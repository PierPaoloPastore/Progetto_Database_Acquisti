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
    abort,
)

from app.models import Invoice
from app.services import (
    search_invoices,
    get_invoice_detail,
    update_invoice_status,
    confirm_invoice as confirm_invoice_service,
    reject_invoice as reject_invoice_service,
    list_invoices_to_review,
    list_invoices_without_physical_copy,
    get_next_invoice_to_review,
    request_physical_copy,
    mark_physical_copy_received,
)
from app.services.invoice_service import InvoiceService
from app.services.dto import InvoiceSearchFilters
from app.repositories import (
    list_suppliers,
    list_legal_entities,
    list_accounting_years,
    get_invoice_by_id,
)

invoices_bp = Blueprint("invoices", __name__)


ALLOWED_PHYSICAL_COPY_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tif", "tiff"}


def _is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHYSICAL_COPY_EXTENSIONS


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


@invoices_bp.route("/review/list", methods=["GET"])
def review_list_view():
    """Pagina dedicata alle fatture importate da rivedere."""
    order = request.args.get("order", "desc")
    invoices = list_invoices_to_review(order=order)
    next_invoice = get_next_invoice_to_review(order=order)

    return render_template(
        "invoices/review_list.html",
        invoices=invoices,
        next_invoice=next_invoice,
        order=order,
    )


@invoices_bp.route("/review", methods=["GET"])
def review_loop_redirect_view():
    """Reindirizza alla prossima fattura da rivedere oppure alla lista."""

    next_invoice = InvoiceService.get_next_invoice_to_review()
    if next_invoice:
        return redirect(
            url_for(
                "invoices.review_loop_invoice_view",
                invoice_id=next_invoice.id,
            )
        )

    flash("Tutte le fatture importate sono state gestite.", "success")
    return redirect(url_for("invoices.list_view"))


@invoices_bp.route("/review/<int:invoice_id>", methods=["GET", "POST"])
def review_loop_invoice_view(invoice_id: int):
    """Pagina di revisione singola fattura con conferma rapida."""

    if request.method == "POST":
        success, message = InvoiceService.review_and_confirm(
            invoice_id, request.form.to_dict()
        )
        if not success:
            if message == "Fattura non trovata":
                abort(404)

            flash(message, "danger")
        else:
            flash("Fattura confermata e passata alla successiva.", "success")
            return redirect(url_for("invoices.review_loop_redirect_view"))

    invoice = InvoiceService.get_invoice_by_id(invoice_id)
    if invoice is None:
        abort(404)

    return render_template('invoices/review.html', invoice=invoice)


@invoices_bp.route(
    "/preview/<int:invoice_id>", methods=["GET"], endpoint="preview_invoice_visual"
)
def preview_invoice_visual(invoice_id: int):
    """Mostra l'anteprima della fattura per l'iframe di revisione."""

    invoice = InvoiceService.get_invoice_by_id(invoice_id)
    if invoice is None:
        abort(404)

    return render_template("invoices/preview_template.html", invoice=invoice)


@invoices_bp.route("/physical-copies", methods=["GET"])
def physical_copy_list_view():
    """To-do list delle fatture senza copia fisica o con copia richiesta."""
    invoices = list_invoices_without_physical_copy(order=request.args.get("order", "desc"))
    return render_template(
        "invoices/physical_copy_list.html",
        invoices=invoices,
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
    allowed_doc_statuses = {
        "imported",
        "pending_physical_copy",
        "verified",
        "rejected",
        "archived",
    }

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


@invoices_bp.route("/<int:invoice_id>/confirm", methods=["POST"])
def confirm_invoice(invoice_id: int):
    """Conferma una fattura importata e passa alla successiva da rivedere."""
    order = request.args.get("order", "desc")
    invoice = get_invoice_by_id(invoice_id)

    if invoice is None:
        abort(404)

    if invoice.doc_status != "imported":
        flash("La fattura non è in stato 'imported'.", "warning")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice.id, order=order))

    confirm_invoice_service(invoice_id)
    flash("Fattura confermata.", "success")

    next_invoice = get_next_invoice_to_review(order=order)
    if next_invoice:
        return redirect(
            url_for("invoices.detail_view", invoice_id=next_invoice.id, order=order)
        )

    flash("Nessun'altra fattura da rivedere.", "info")
    return redirect(url_for("invoices.review_list_view", order=order))


@invoices_bp.route("/<int:invoice_id>/reject", methods=["POST"])
def reject_invoice(invoice_id: int):
    """Scarta una fattura importata e passa alla successiva da rivedere."""
    order = request.args.get("order", "desc")
    invoice = get_invoice_by_id(invoice_id)

    if invoice is None:
        abort(404)

    if invoice.doc_status != "imported":
        flash("La fattura non è in stato 'imported'.", "warning")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice.id, order=order))

    reject_invoice_service(invoice_id)
    flash("Fattura scartata.", "success")

    next_invoice = get_next_invoice_to_review(order=order)
    if next_invoice:
        return redirect(
            url_for("invoices.detail_view", invoice_id=next_invoice.id, order=order)
        )

    flash("Nessun'altra fattura da rivedere.", "info")
    return redirect(url_for("invoices.review_list_view", order=order))


@invoices_bp.route(
    "/<int:invoice_id>/physical-copy/request",
    methods=["POST"],
    endpoint="request_physical_copy",
)
def request_physical_copy_view(invoice_id: int):
    """Richiede la copia cartacea della fattura al fornitore."""
    invoice = request_physical_copy(invoice_id)

    if invoice is None:
        abort(404)

    flash("Richiesta copia fisica registrata.", "success")

    return redirect(url_for("invoices.detail_view", invoice_id=invoice.id))


@invoices_bp.route(
    "/<int:invoice_id>/physical-copy/received",
    methods=["POST"],
    endpoint="mark_physical_copy_received",
)
def mark_physical_copy_received_view(invoice_id: int):
    """Segna come ricevuta la copia cartacea della fattura."""
    invoice = mark_physical_copy_received(invoice_id, file=None)

    if invoice is None:
        abort(404)

    flash("Copia fisica segnata come ricevuta.", "success")

    return redirect(url_for("invoices.detail_view", invoice_id=invoice.id))


@invoices_bp.route(
    "/<int:invoice_id>/physical-copy/upload",
    methods=["POST"],
    endpoint="upload_physical_copy",
)
def upload_physical_copy_view(invoice_id: int):
    """Carica e collega una scansione per la copia fisica."""
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Seleziona un file da caricare.", "warning")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))

    if not _is_allowed_file(file.filename):
        flash("Formato file non supportato. Carica PDF o immagini.", "danger")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))

    try:
        invoice = mark_physical_copy_received(invoice_id, file=file)
    except Exception as exc:  # pragma: no cover - gestione runtime
        flash(f"Errore nel salvataggio della copia fisica: {exc}", "danger")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))

    if invoice is None:
        abort(404)

    flash("Copia fisica caricata e segnata come ricevuta.", "success")

    return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))


@invoices_bp.get("/<int:invoice_id>/attach-scan")
def attach_scan_view(invoice_id: int):
    invoice = Invoice.query.get_or_404(invoice_id)

    from app.services.scan_service import list_inbox_files

    files = list_inbox_files()

    return render_template(
        "invoices/attach_scan.html",
        invoice=invoice,
        inbox_files=files,
    )


@invoices_bp.post("/<int:invoice_id>/attach-scan")
def attach_scan_process(invoice_id: int):
    invoice = Invoice.query.get_or_404(invoice_id)
    filename = request.form.get("selected_file")

    if not filename:
        flash("Seleziona un file prima di procedere.", "warning")
        return redirect(url_for("invoices.attach_scan_view", invoice_id=invoice_id))

    from app.services.scan_service import attach_scan_to_invoice

    try:
        attach_scan_to_invoice(filename, invoice)
        flash("Scansione collegata correttamente.", "success")
    except Exception as e:  # pragma: no cover - gestione errori runtime
        flash(f"Errore: {e}", "danger")

    return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))
