"""
Route per la gestione dei Documenti.
"""
from __future__ import annotations

import os
from datetime import datetime, date
from typing import Optional
from flask import (
    Blueprint, render_template, render_template_string, request, redirect, url_for, flash, abort, send_file, current_app
)

from app.models import Document
from app.services import document_service as doc_service
from app.services.document_service import DocumentService, render_invoice_html
from app.services.dto import DocumentSearchFilters

# FIX: Import dai service invece che dai repo diretti dove possibile
from app.services.supplier_service import list_active_suppliers
from app.repositories.legal_entity_repo import list_legal_entities
from app.services.delivery_note_service import (
    find_delivery_note_candidates,
    list_delivery_notes_by_document,
    link_delivery_note_to_document,
)

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
    sort_field = request.args.get("sort") or None
    sort_dir = request.args.get("dir") or "desc"
    
    documents = doc_service.search_documents(filters=filters, limit=300, document_type=None)
    if sort_field in {"date", "number"}:
        reverse = (sort_dir == "desc")
        if sort_field == "date":
            documents = sorted(
                documents,
                key=lambda d: d.document_date or date.min,
                reverse=reverse,
            )
        elif sort_field == "number":
            documents = sorted(
                documents,
                key=lambda d: (d.document_number or "").lower(),
                reverse=reverse,
            )
    else:
        # Ordinamento di default: da rivedere -> verificati non pagati -> pagati/archiviati
        status_priority = {
            "pending_physical_copy": 0,
            "verified": 1,
            "archived": 2,
        }
        documents = sorted(
            documents,
            key=lambda d: (
                status_priority.get(d.doc_status, 5),
                0 if not getattr(d, "is_paid", False) else 1,
                -(d.document_date.toordinal() if d.document_date else date.min.toordinal()),
                -d.id,
            ),
        )

    suppliers = list_active_suppliers()
    legal_entities = list_legal_entities(include_inactive=False)
    
    # FIX: Chiamata al service invece che al repo
    accounting_years = doc_service.get_accounting_years()
    base_query_args = {k: v for k, v in request.args.to_dict().items() if k not in {"sort", "dir"}}
    date_dir = "asc" if sort_field != "date" or sort_dir == "desc" else "desc"
    number_dir = "asc" if sort_field != "number" or sort_dir == "desc" else "desc"
    date_url = url_for("documents.list_view", **base_query_args, sort="date", dir=date_dir)
    number_url = url_for("documents.list_view", **base_query_args, sort="number", dir=number_dir)

    return render_template(
        "documents/list.html",
        documents=documents,
        suppliers=suppliers,
        legal_entities=legal_entities,
        accounting_years=accounting_years,
        filters=filters,
        sort_field=sort_field,
        sort_dir=sort_dir,
        base_query_args=base_query_args,
        date_url=date_url,
        number_url=number_url,
    )

@documents_bp.route("/review/list", methods=["GET"])
def review_list_view():
    order = request.args.get("order", "desc")
    raw_legal_entity_id = request.args.get("legal_entity_id") or None
    legal_entity_id = None
    if raw_legal_entity_id:
        try:
            legal_entity_id = int(raw_legal_entity_id)
        except ValueError:
            legal_entity_id = None

    documents = doc_service.list_documents_to_review(
        order=order,
        document_type="invoice",
        legal_entity_id=legal_entity_id,
    )
    next_doc = doc_service.get_next_document_to_review(
        order=order,
        document_type="invoice",
        legal_entity_id=legal_entity_id,
    )
    from app.repositories.legal_entity_repo import list_legal_entities
    legal_entities = list_legal_entities(include_inactive=False)
    le_counts = doc_service.count_documents_to_review_by_legal_entity()

    return render_template(
        "documents/review_list.html",
        invoices=documents, 
        next_invoice=next_doc,
        legal_entities=legal_entities,
        selected_legal_entity_id=legal_entity_id,
        le_counts=le_counts,
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
        action = request.form.get("action") or "review"
        if action == "review":
            success, message = DocumentService.review_and_confirm(document_id, request.form.to_dict())
            if not success:
                if message == "Documento non trovato": abort(404)
                flash(message, "danger")
            else:
                flash("Documento confermato e passato al successivo.", "success")
                return redirect(url_for("documents.review_loop_redirect_view"))
        elif action == "match_ddt":
            delivery_note_id = request.form.get("delivery_note_id")
            status = request.form.get("ddt_status") or "matched"
            if not delivery_note_id:
                flash("Seleziona un DDT da abbinare.", "warning")
            else:
                try:
                    link_delivery_note_to_document(int(delivery_note_id), document_id, status=status)
                    flash("DDT abbinato con successo.", "success")
                except Exception as exc:
                    flash(f"Errore in abbinamento DDT: {exc}", "danger")
        elif action == "upload_physical_copy":
            file = request.files.get("physical_copy_file")
            if file is None or not file.filename:
                flash("Seleziona un file PDF da caricare.", "warning")
            else:
                doc = doc_service.mark_physical_copy_received(document_id, file=file)
                if doc is None:
                    flash("Documento non trovato.", "warning")
                else:
                    flash("Copia fisica caricata e collegata.", "success")

    document = DocumentService.get_document_by_id(document_id)
    if document is None: abort(404)
    from app.services.settings_service import get_setting
    default_xsl = get_setting("DEFAULT_XSL_STYLE", "ordinaria")

    # DDT candidati e collegati
    ddt_candidates = []
    if document.supplier_id:
        ddt_candidates = find_delivery_note_candidates(
            supplier_id=document.supplier_id,
            ddt_number=request.args.get("ddt_number") or None,
            ddt_date=None,  # lasciamo filtro data libero per ora
            allowed_statuses=["unmatched", "linked"],
            limit=200,
            exclude_document_ids=[document_id],
        )
    linked_ddt = list_delivery_notes_by_document(document_id) if document else []
    attachments = doc_service.list_document_attachments(document_id)

    return render_template(
        'documents/review.html',
        invoice=document,
        today=date.today(),
        default_xsl=default_xsl,
        ddt_candidates=ddt_candidates,
        linked_ddt=linked_ddt,
        attachments=attachments,
    )

@documents_bp.route("/review/<int:document_id>/delete", methods=["POST"])
def delete_document(document_id: int):
    ok = DocumentService.delete_document(document_id)
    if not ok:
        abort(404)
    flash("Documento scartato ed eliminato. Potrai reimportarlo.", "info")
    return redirect(url_for("documents.review_loop_redirect_view"))

    
@documents_bp.route("/preview/<int:document_id>", methods=["GET"], endpoint="preview_visual")
def preview_visual(document_id: int):
    document = DocumentService.get_document_by_id(document_id)
    if document is None:
        abort(404)

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "storage/uploads")
    xml_full_path = None

    if document.file_path:
        if os.path.isabs(document.file_path):
             xml_full_path = document.file_path
        else:
             xml_full_path = os.path.join(upload_folder, document.file_path)

    elif document.import_source:
        candidate_path = document.import_source
        if candidate_path.lower().endswith(('.xml', '.p7m', '.xml.p7m')):
            xml_full_path = candidate_path
        elif document.file_name:
            xml_full_path = os.path.join(candidate_path, document.file_name)
        else:
            xml_full_path = candidate_path
    
    else:
        return "<h1>Errore</h1><p>Nessun percorso file presente nel database.</p>", 404

    # Seleziona XSL da querystring (fogli di stile AE)
    # Tre opzioni esposte: Asso (custom), Ordinaria (AE) e Semplificata VFSM10 (AE)
    style_map = {
        "asso": "FoglioStileAssoSoftware.xsl",
        # scegliamo l'ordinaria come foglio AE predefinito
        "ordinaria": "Foglio_di_stile_fattura_ordinaria_ver1.2.3.xsl",
        "vfsm10": "Foglio_di_stile_VFSM10_v1.0.2.xsl",
    }
    style_key = request.args.get("style", "ordinaria")
    xsl_name = style_map.get(style_key, style_map["ordinaria"])
    # resources/ vive alla radice del progetto (un livello sopra current_app.root_path)
    base_dir = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    xsl_full_path = os.path.join(base_dir, "resources", "xsl", xsl_name)

    try:
        html_content = render_invoice_html(xml_full_path, xsl_full_path)
        return render_template_string(html_content)
    except FileNotFoundError:
        return f"<h1>File non trovato</h1><p>Il sistema ha cercato qui:<br><code>{xml_full_path}</code><br>Ma il file non esiste.</p>", 404
    except Exception as e:
        return f"<h1>Errore di visualizzazione</h1><p>{str(e)}</p>", 500

@documents_bp.route("/<int:document_id>", methods=["GET"])
def detail_view(document_id: int):
    detail = doc_service.get_document_detail(document_id)
    if detail is None:
        flash("Documento non trovato.", "warning")
        return redirect(url_for("documents.list_view"))

    # DDT collegati a questa fattura (match manuale)
    from app.services.delivery_note_service import (
        list_delivery_notes_by_document,
    )
    detail["linked_delivery_notes"] = list_delivery_notes_by_document(document_id)

    return render_template("documents/detail.html", **detail)


@documents_bp.route("/<int:document_id>/attachments/<path:filename>", methods=["GET"])
def download_attachment(document_id: int, filename: str):
    from app.services.settings_service import get_attachments_storage_path
    safe_name = os.path.basename(filename)
    base_dir = get_attachments_storage_path()
    full_path = os.path.join(base_dir, str(document_id), safe_name)
    if not os.path.exists(full_path):
        abort(404)
    return send_file(full_path, as_attachment=True, download_name=safe_name)


@documents_bp.route("/<int:document_id>/match-ddt", methods=["GET", "POST"])
def match_delivery_notes_view(document_id: int):
    invoice = DocumentService.get_document_by_id(document_id)
    if invoice is None:
        flash("Documento non trovato.", "warning")
        return redirect(url_for("documents.list_view"))

    if request.method == "POST":
        delivery_note_id = request.form.get("delivery_note_id")
        status = request.form.get("status") or "matched"
        if not delivery_note_id:
            flash("Seleziona un DDT.", "warning")
            return redirect(url_for("documents.match_delivery_notes_view", document_id=document_id))
        try:
            link_delivery_note_to_document(int(delivery_note_id), document_id, status=status)
            flash("DDT abbinato con successo.", "success")
        except Exception as exc:
            flash(f"Errore in abbinamento: {exc}", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))

    supplier_id = invoice.supplier_id
    candidates = []
    if supplier_id:
        candidates = find_delivery_note_candidates(
            supplier_id=supplier_id,
            allowed_statuses=["unmatched", "linked"],
            limit=200,
        )

    return render_template(
        "documents/match_delivery_notes.html",
        invoice=invoice,
        candidates=candidates,
    )

@documents_bp.route("/<int:document_id>/status", methods=["POST"])
def update_status_view(document_id: int):
    allowed_doc_statuses = {"pending_physical_copy", "verified", "archived"}
    doc_status = request.form.get("doc_status") or None
    
    if doc_status is not None and doc_status not in allowed_doc_statuses:
        flash("Valore di stato documento non valido.", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))
    
    due_date_str = request.form.get("due_date") or ""
    due_date = _parse_date(due_date_str)
    note = request.form.get("note")

    doc = doc_service.update_document_status(document_id=document_id, doc_status=doc_status, due_date=due_date, note=note)
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
    flash("Documento archiviato.", "success")
    next_invoice = doc_service.get_next_document_to_review(order=order, document_type=None)
    if next_invoice:
        return redirect(url_for("documents.detail_view", document_id=next_invoice.id, order=order))
    flash("Nessun altro documento da rivedere.", "info")
    return redirect(url_for("documents.review_list_view", order=order))

@documents_bp.get("/<int:document_id>/attach-scan")
def attach_scan_view(document_id: int):
    document = Document.query.get_or_404(document_id)
    return render_template("documents/attach_scan.html", invoice=document)

@documents_bp.post("/<int:document_id>/attach-scan")
def attach_scan_process(document_id: int):
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
