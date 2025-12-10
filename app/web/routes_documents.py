"""
Route per la gestione dei Documenti (ex Invoices).
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
)

from app.models import Document
from app.services import document_service as doc_service
from app.services.document_service import DocumentService
from app.services.dto import DocumentSearchFilters
from app.repositories.document_repo import list_accounting_years
from app.repositories.supplier_repo import list_suppliers
from app.repositories.legal_entity_repo import list_legal_entities

documents_bp = Blueprint("documents", __name__)

ALLOWED_PHYSICAL_COPY_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tif", "tiff"}

def _is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHYSICAL_COPY_EXTENSIONS

def _parse_date(value: str) -> Optional[datetime.date]:
    if not value: return None
    try: return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError: return None


@documents_bp.route("/", methods=["GET"])
def list_view():
    filters = DocumentSearchFilters.from_query_args(request.args)
    documents = doc_service.search_documents(filters=filters, limit=300, document_type=None)
    suppliers = list_suppliers(include_inactive=False)
    legal_entities = list_legal_entities(include_inactive=False)
    accounting_years = list_accounting_years()

    # FIX: path template aggiornato a 'documents/'
    return render_template(
        "documents/list.html",
        documents=documents,
        suppliers=suppliers,
        legal_entities=legal_entities,
        accounting_years=accounting_years,
        filters=filters,
    )


@documents_bp.route("/review/list", methods=["GET"])
def review_list_view():
    order = request.args.get("order", "desc")
    documents = doc_service.list_documents_to_review(order=order, document_type=None)
    next_doc = doc_service.get_next_document_to_review(order=order, document_type=None)

    # FIX: path template aggiornato
    return render_template(
        "documents/review_list.html",
        invoices=documents, 
        next_invoice=next_doc,
        order=order,
    )


@documents_bp.route("/review", methods=["GET"])
def review_loop_redirect_view():
    next_doc = doc_service.get_next_document_to_review(document_type=None)
    if next_doc:
        return redirect(url_for("documents.review_loop_invoice_view", document_id=next_doc.id))
    flash("Tutti i documenti importati sono stati gestiti.", "success")
    return redirect(url_for("documents.list_view"))


@documents_bp.route("/review/<int:document_id>", methods=["GET", "POST"])
def review_loop_invoice_view(document_id: int):
    if request.method == "POST":
        success, message = DocumentService.review_and_confirm(document_id, request.form.to_dict())
        if not success:
            if message == "Documento non trovato": abort(404)
            flash(message, "danger")
        else:
            flash("Documento confermato e passato al successivo.", "success")
            return redirect(url_for("documents.review_loop_redirect_view"))

    document = DocumentService.get_document_by_id(document_id)
    if document is None: abort(404)
    # FIX: path template aggiornato
    return render_template('documents/review.html', invoice=document)


@documents_bp.route("/preview/<int:document_id>", methods=["GET"], endpoint="preview_visual")
def preview_visual(document_id: int):
    document = DocumentService.get_document_by_id(document_id)
    if document is None: abort(404)
    # FIX: path template aggiornato
    return render_template("documents/preview_template.html", invoice=document)


@documents_bp.route("/<int:document_id>", methods=["GET"])
def detail_view(document_id: int):
    detail = doc_service.get_document_detail(document_id)
    if detail is None:
        flash("Documento non trovato.", "warning")
        return redirect(url_for("documents.list_view"))
    # FIX: path template aggiornato
    return render_template("documents/detail.html", **detail)


@documents_bp.route("/<int:document_id>/status", methods=["POST"])
def update_status_view(document_id: int):
    allowed_doc_statuses = {"imported", "pending_physical_copy", "verified", "rejected", "archived"}
    doc_status = request.form.get("doc_status") or None
    if doc_status is not None and doc_status not in allowed_doc_statuses:
        flash("Valore di stato documento non valido.", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))
    
    due_date_str = request.form.get("due_date") or ""
    due_date = _parse_date(due_date_str)

    doc = doc_service.update_document_status(document_id=document_id, doc_status=doc_status, due_date=due_date)
    if doc is None:
        flash("Documento non trovato.", "danger")
    else:
        flash("Stato aggiornato con successo.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))


@documents_bp.route("/<int:document_id>/confirm", methods=["POST"])
def confirm_invoice(document_id: int):
    order = request.args.get("order", "desc")
    invoice = doc_service.confirm_document(document_id)
    if invoice is None: abort(404)
    flash("Documento confermato.", "success")
    
    next_invoice = doc_service.get_next_document_to_review(order=order, document_type=None)
    if next_invoice:
        return redirect(url_for("documents.detail_view", document_id=next_invoice.id, order=order))
    flash("Nessun altro documento da rivedere.", "info")
    return redirect(url_for("documents.review_list_view", order=order))


@documents_bp.route("/<int:document_id>/reject", methods=["POST"])
def reject_invoice(document_id: int):
    order = request.args.get("order", "desc")
    invoice = doc_service.reject_document(document_id)
    if invoice is None: abort(404)
    flash("Documento scartato.", "success")

    next_invoice = doc_service.get_next_document_to_review(order=order, document_type=None)
    if next_invoice:
        return redirect(url_for("documents.detail_view", document_id=next_invoice.id, order=order))
    flash("Nessun altro documento da rivedere.", "info")
    return redirect(url_for("documents.review_list_view", order=order))


@documents_bp.route("/<int:document_id>/physical-copy/request", methods=["POST"], endpoint="request_physical_copy")
def request_physical_copy_view(document_id: int):
    invoice = doc_service.request_physical_copy(document_id)
    if invoice is None: abort(404)
    flash("Richiesta copia fisica registrata.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))


@documents_bp.route("/<int:document_id>/physical-copy/received", methods=["POST"], endpoint="mark_physical_copy_received")
def mark_physical_copy_received_view(document_id: int):
    invoice = doc_service.mark_physical_copy_received(document_id, file=None)
    if invoice is None: abort(404)
    flash("Copia fisica segnata come ricevuta.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))


@documents_bp.route("/<int:document_id>/physical-copy/upload", methods=["POST"], endpoint="upload_physical_copy")
def upload_physical_copy_view(document_id: int):
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Seleziona un file da caricare.", "warning")
        return redirect(url_for("documents.detail_view", document_id=document_id))
    if not _is_allowed_file(file.filename):
        flash("Formato file non supportato.", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))

    doc = doc_service.mark_physical_copy_received(document_id, file=file)
    if doc is None: abort(404)
    flash("Copia fisica caricata.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))

@documents_bp.route("/<int:document_id>/attach-scan", methods=["GET"])
def attach_scan_view(document_id: int):
    """Mostra il form per caricare una scansione direttamente."""
    document = Document.query.get_or_404(document_id)
    # Non chiamiamo più list_inbox_files(), non serve per l'upload diretto
    return render_template("documents/attach_scan.html", invoice=document)


@documents_bp.route("/<int:document_id>/attach-scan", methods=["POST"])
def attach_scan_process(document_id: int):
    """Gestisce l'upload del file di scansione."""
    document = Document.query.get_or_404(document_id)
    
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Seleziona un file da caricare.", "warning")
        return redirect(url_for("documents.attach_scan_view", document_id=document_id))

    if not _is_allowed_file(file.filename):
        flash("Formato file non supportato (usa PDF, JPG, PNG).", "danger")
        return redirect(url_for("documents.attach_scan_view", document_id=document_id))

    # Usiamo la funzione esistente nel service che gestisce già salvataggio e aggiornamento DB
    doc_service.mark_physical_copy_received(document_id, file=file)
    
    flash("Scansione caricata e collegata correttamente.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))