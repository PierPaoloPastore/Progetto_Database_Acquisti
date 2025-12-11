"""
Route per la gestione dei Documenti.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional
from app.services.document_service import render_invoice_html # Importa la nuova funzione
from flask import (
    Blueprint, render_template,render_template_string, request, redirect, url_for, flash, abort,send_file,current_app
)

from app.models import Document
from app.services import document_service as doc_service
from app.services.document_service import DocumentService
# FIX: Importa DocumentSearchFilters
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
    # FIX: Usa DocumentSearchFilters
    filters = DocumentSearchFilters.from_query_args(request.args)
    
    documents = doc_service.search_documents(filters=filters, limit=300, document_type=None)

    suppliers = list_suppliers(include_inactive=False)
    legal_entities = list_legal_entities(include_inactive=False)
    accounting_years = list_accounting_years()

    return render_template(
        "documents/list.html",
        documents=documents,
        suppliers=suppliers,
        legal_entities=legal_entities,
        accounting_years=accounting_years,
        filters=filters,
    )

# ... (il resto del file rimane uguale, assicurati di avere from __future__ in cima) ...
# [Copia il resto del file routes_documents.py che avevi, la parte importante è l'import e la funzione list_view]
@documents_bp.route("/review/list", methods=["GET"])
def review_list_view():
    order = request.args.get("order", "desc")
    documents = doc_service.list_documents_to_review(order=order, document_type=None)
    next_doc = doc_service.get_next_document_to_review(order=order, document_type=None)

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
    return render_template('documents/review.html', invoice=document)

    
@documents_bp.route("/preview/<int:document_id>", methods=["GET"], endpoint="preview_visual")
def preview_visual(document_id: int):
    # 1. Recupera il documento
    document = DocumentService.get_document_by_id(document_id)
    if document is None:
        abort(404)

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "storage/uploads")
    xml_full_path = None

    # --- LOGICA DI RISOLUZIONE DEL PERCORSO ---
    
    # CASO A: Il file è nello storage interno (file_path popolato)
    if document.file_path:
        # Se è assoluto (es. vecchi test), usalo diretto
        if os.path.isabs(document.file_path):
             xml_full_path = document.file_path
        else:
             # Normale: uniamo alla cartella uploads
             xml_full_path = os.path.join(upload_folder, document.file_path)

    # CASO B: Usiamo la sorgente originale (import_source)
    elif document.import_source:
        candidate_path = document.import_source
        
        # Verifica euristica: Se finisce per .xml o .p7m è probabilmente un file completo
        if candidate_path.lower().endswith(('.xml', '.p7m', '.xml.p7m')):
            xml_full_path = candidate_path
        
        # Se NON ha estensione (è una cartella) e abbiamo il file_name, li uniamo
        elif document.file_name:
            xml_full_path = os.path.join(candidate_path, document.file_name)
        
        # Fallback
        else:
            xml_full_path = candidate_path
    
    else:
        return "<h1>Errore</h1><p>Nessun percorso file presente nel database.</p>", 404

    # --- RENDERING ---
    xsl_full_path = os.path.join(current_app.root_path, "static", "xsl", "FoglioStileAssoSoftware.xsl")

    try:
        html_content = render_invoice_html(xml_full_path, xsl_full_path)
        return render_template_string(html_content)
    except FileNotFoundError:
        return f"<h1>File non trovato</h1><p>Il sistema ha cercato qui:<br><code>{xml_full_path}</code><br>Ma il file non esiste (forse è stato spostato o cancellato).</p>", 404
    except Exception as e:
        return f"<h1>Errore di visualizzazione</h1><p>{str(e)}</p>", 500
@documents_bp.route("/<int:document_id>", methods=["GET"])
def detail_view(document_id: int):
    detail = doc_service.get_document_detail(document_id)
    if detail is None:
        flash("Documento non trovato.", "warning")
        return redirect(url_for("documents.list_view"))
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

@documents_bp.get("/<int:document_id>/attach-scan")
def attach_scan_view(document_id: int):
    """Mostra il form per caricare una scansione direttamente."""
    document = Document.query.get_or_404(document_id)
    return render_template("documents/attach_scan.html", invoice=document)

@documents_bp.post("/<int:document_id>/attach-scan")
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

    doc_service.mark_physical_copy_received(document_id, file=file)
    
    flash("Scansione caricata e collegata correttamente.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))

@documents_bp.route("/<int:document_id>/physical-copy/view", methods=["GET"])
def view_physical_copy(document_id: int):
    """Serve il file della copia fisica al browser."""
    document = Document.query.get_or_404(document_id)
    
    if not document.physical_copy_file_path:
        abort(404)

    from app.services.settings_service import get_physical_copy_storage_path
    base_path = get_physical_copy_storage_path()
    
    full_path = os.path.join(base_path, document.physical_copy_file_path)
    
    if not os.path.exists(full_path):
        flash("File fisico non trovato sul disco.", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))

    return send_file(full_path, as_attachment=False)

@documents_bp.route("/<int:document_id>/physical-copy/remove", methods=["POST"])
def remove_physical_copy(document_id: int):
    """Rimuove il collegamento alla copia fisica."""
    document = Document.query.get_or_404(document_id)
    
    if not document.physical_copy_file_path:
        flash("Nessuna copia fisica da rimuovere.", "warning")
        return redirect(url_for("documents.detail_view", document_id=document_id))

    from app.extensions import db
    
    previous_path = document.physical_copy_file_path
    document.physical_copy_file_path = None
    document.physical_copy_status = "missing" 
    document.physical_copy_received_at = None
    
    db.session.add(document)
    db.session.commit()
    
    flash(f"Collegamento rimosso. (Il file {os.path.basename(previous_path)} è rimasto in archivio)", "info")
    return redirect(url_for("documents.detail_view", document_id=document_id))