"""
Route per la gestione delle fatture (Invoice -> Document).
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)

from app.models import Document
# Importiamo il NUOVO servizio DocumentService
from app.services import document_service as doc_service
from app.services.document_service import DocumentService # Classe statica
from app.services.dto import InvoiceSearchFilters
# Importiamo funzioni helper dal NUOVO repo (DocumentRepo)
from app.repositories.document_repo import list_accounting_years
from app.repositories.supplier_repo import list_suppliers
from app.repositories.legal_entity_repo import list_legal_entities

invoices_bp = Blueprint("invoices", __name__)
ALLOWED_PHYSICAL_COPY_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tif", "tiff"}

def _is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHYSICAL_COPY_EXTENSIONS

def _parse_date(value: str) -> Optional[datetime.date]:
    if not value: return None
    try: return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError: return None


@invoices_bp.route("/", methods=["GET"])
def list_view():
    filters = InvoiceSearchFilters.from_query_args(request.args)
    
    # Chiamiamo search_documents filtrando per TYPE='invoice'
    invoices = doc_service.search_documents(filters=filters, limit=300, document_type='invoice')

    suppliers = list_suppliers(include_inactive=False)
    legal_entities = list_legal_entities(include_inactive=False)
    accounting_years = list_accounting_years() # Ora in document_repo

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
    filters = InvoiceSearchFilters.from_query_args(request.args)
    if filters.doc_status is None:
        filters.doc_status = "imported"

    invoices = doc_service.search_documents(filters=filters, limit=300, document_type='invoice')

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
    order = request.args.get("order", "desc")
    invoices = doc_service.list_documents_to_review(order=order, document_type='invoice')
    next_invoice = doc_service.get_next_document_to_review(order=order, document_type='invoice')

    return render_template(
        "invoices/review_list.html",
        invoices=invoices,
        next_invoice=next_invoice,
        order=order,
    )


@invoices_bp.route("/review", methods=["GET"])
def review_loop_redirect_view():
    next_invoice = DocumentService.get_next_invoice_to_review()
    if next_invoice:
        return redirect(url_for("invoices.review_loop_invoice_view", invoice_id=next_invoice.id))
    flash("Tutte le fatture importate sono state gestite.", "success")
    return redirect(url_for("invoices.list_view"))


@invoices_bp.route("/review/<int:invoice_id>", methods=["GET", "POST"])
def review_loop_invoice_view(invoice_id: int):
    if request.method == "POST":
        success, message = DocumentService.review_and_confirm(invoice_id, request.form.to_dict())
        if not success:
            if message == "Documento non trovato": abort(404)
            flash(message, "danger")
        else:
            flash("Fattura confermata e passata alla successiva.", "success")
            return redirect(url_for("invoices.review_loop_redirect_view"))

    invoice = DocumentService.get_document_by_id(invoice_id)
    if invoice is None: abort(404)
    return render_template('invoices/review.html', invoice=invoice)


@invoices_bp.route("/preview/<int:invoice_id>", methods=["GET"], endpoint="preview_invoice_visual")
def preview_invoice_visual(invoice_id: int):
    invoice = DocumentService.get_document_by_id(invoice_id)
    if invoice is None: abort(404)
    return render_template("invoices/preview_template.html", invoice=invoice)


@invoices_bp.route("/physical-copies", methods=["GET"])
def physical_copy_list_view():
    # Nota: qui potresti voler filtrare per type='invoice' se list_documents_without_physical_copy non lo fa
    invoices = doc_service.list_documents_without_physical_copy(order=request.args.get("order", "desc"))
    return render_template("invoices/physical_copy_list.html", invoices=invoices)


@invoices_bp.route("/<int:invoice_id>", methods=["GET"])
def detail_view(invoice_id: int):
    detail = doc_service.get_document_detail(invoice_id)
    if detail is None:
        flash("Fattura non trovata.", "warning")
        return redirect(url_for("invoices.list_view"))
    return render_template("invoices/detail.html", **detail)


@invoices_bp.route("/<int:invoice_id>/status", methods=["POST"])
def update_status_view(invoice_id: int):
    allowed_doc_statuses = {"imported", "pending_physical_copy", "verified", "rejected", "archived"}
    doc_status = request.form.get("doc_status") or None
    if doc_status is not None and doc_status not in allowed_doc_statuses:
        flash("Valore di stato documento non valido.", "danger")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))
    
    due_date_str = request.form.get("due_date") or ""
    due_date = _parse_date(due_date_str)

    invoice = doc_service.update_document_status(
        document_id=invoice_id,
        doc_status=doc_status,
        due_date=due_date,
    )
    if invoice is None:
        flash("Fattura non trovata o errore di aggiornamento.", "danger")
    else:
        flash("Stato fattura aggiornato con successo.", "success")
    return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))


@invoices_bp.route("/<int:invoice_id>/confirm", methods=["POST"])
def confirm_invoice(invoice_id: int):
    order = request.args.get("order", "desc")
    invoice = doc_service.confirm_document(invoice_id)
    if invoice is None: abort(404)
    flash("Fattura confermata.", "success")
    
    next_invoice = doc_service.get_next_document_to_review(order=order, document_type='invoice')
    if next_invoice:
        return redirect(url_for("invoices.detail_view", invoice_id=next_invoice.id, order=order))
    flash("Nessun'altra fattura da rivedere.", "info")
    return redirect(url_for("invoices.review_list_view", order=order))


@invoices_bp.route("/<int:invoice_id>/reject", methods=["POST"])
def reject_invoice(invoice_id: int):
    order = request.args.get("order", "desc")
    invoice = doc_service.reject_document(invoice_id)
    if invoice is None: abort(404)
    flash("Fattura scartata.", "success")

    next_invoice = doc_service.get_next_document_to_review(order=order, document_type='invoice')
    if next_invoice:
        return redirect(url_for("invoices.detail_view", invoice_id=next_invoice.id, order=order))
    flash("Nessun'altra fattura da rivedere.", "info")
    return redirect(url_for("invoices.review_list_view", order=order))


@invoices_bp.route("/<int:invoice_id>/physical-copy/request", methods=["POST"], endpoint="request_physical_copy")
def request_physical_copy_view(invoice_id: int):
    invoice = doc_service.request_physical_copy(invoice_id)
    if invoice is None: abort(404)
    flash("Richiesta copia fisica registrata.", "success")
    return redirect(url_for("invoices.detail_view", invoice_id=invoice.id))


@invoices_bp.route("/<int:invoice_id>/physical-copy/received", methods=["POST"], endpoint="mark_physical_copy_received")
def mark_physical_copy_received_view(invoice_id: int):
    invoice = doc_service.mark_physical_copy_received(invoice_id, file=None)
    if invoice is None: abort(404)
    flash("Copia fisica segnata come ricevuta.", "success")
    return redirect(url_for("invoices.detail_view", invoice_id=invoice.id))


@invoices_bp.route("/<int:invoice_id>/physical-copy/upload", methods=["POST"], endpoint="upload_physical_copy")
def upload_physical_copy_view(invoice_id: int):
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Seleziona un file da caricare.", "warning")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))
    if not _is_allowed_file(file.filename):
        flash("Formato file non supportato. Carica PDF o immagini.", "danger")
        return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))

    invoice = doc_service.mark_physical_copy_received(invoice_id, file=file)
    if invoice is None: abort(404)
    flash("Copia fisica caricata e segnata come ricevuta.", "success")
    return redirect(url_for("invoices.detail_view", invoice_id=invoice.id))


@invoices_bp.get("/<int:invoice_id>/attach-scan")
def attach_scan_view(invoice_id: int):
    invoice = Document.query.get_or_404(invoice_id)
    from app.services.scan_service import list_inbox_files
    files = list_inbox_files()
    return render_template("invoices/attach_scan.html", invoice=invoice, inbox_files=files)


@invoices_bp.post("/<int:invoice_id>/attach-scan")
def attach_scan_process(invoice_id: int):
    invoice = Document.query.get_or_404(invoice_id)
    filename = request.form.get("selected_file")
    if not filename:
        flash("Seleziona un file prima di procedere.", "warning")
        return redirect(url_for("invoices.attach_scan_view", invoice_id=invoice_id))

    from app.services.scan_service import attach_scan_to_invoice
    try:
        attach_scan_to_invoice(filename, invoice)
        flash("Scansione collegata correttamente.", "success")
    except Exception as e:
        flash(f"Errore: {e}", "danger")
    return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))