"""
Route per la gestione dei Pagamenti.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
import os
from pathlib import Path
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify, current_app, send_file
from sqlalchemy.orm import joinedload

from app.models import Document
from app.services import payment_service, ocr_service, settings_service
from app.services.document_service import mark_documents_as_programmed
from app.services.settings_service import get_setting
from app.services.ocr_mapping_service import parse_payment_fields
from app.services.payment_service import (
    add_payment,
    create_batch_payment,
    delete_payment,
    attach_payment_document_file,
    get_payment_event_detail,
    list_paid_payments,
    list_payments_by_document,
)
from app.services.unit_of_work import UnitOfWork

payments_bp = Blueprint("payments", __name__)

_ALLOWED_PAYMENT_EXTENSIONS = {".pdf"}


def _is_allowed_payment_file(filename: str) -> bool:
    suffix = Path(filename).suffix.lower()
    return suffix in _ALLOWED_PAYMENT_EXTENSIONS

def _resolve_due_status(due_date: date | None, today: date, soon_limit: date) -> tuple[str, str, str]:
    if due_date is None:
        return "no_due", "Senza scadenza", "secondary"
    if due_date < today:
        return "overdue", "Scaduta", "danger"
    if due_date <= soon_limit:
        return "due_soon", "In scadenza", "warning"
    return "scheduled", "Non scaduta", "info"

@payments_bp.route("/", methods=["GET"], endpoint="payment_index")
@payments_bp.route("/", methods=["GET"], endpoint="inbox_view")
def payment_index():
    """
    Mostra la dashboard dei pagamenti (Inbox).
    """
    payment_history = list_paid_payments()

    with UnitOfWork() as uow:
        all_unpaid_invoices = (
            uow.session.query(Document)
            .options(joinedload(Document.supplier))
            .filter(
                Document.document_type == "invoice",
                Document.is_paid == False,
            )
            .order_by(Document.due_date.asc())
            .all()
        )

    payment_service.attach_payment_amounts(all_unpaid_invoices)

    return render_template(
        "payments/inbox.html",
        all_unpaid_invoices=all_unpaid_invoices,
        payment_history=payment_history,
    )


@payments_bp.route("/schedule", methods=["GET"], endpoint="schedule_view")
def schedule_view():
    """
    Scadenziario pagamenti in pagina dedicata.
    """
    today = date.today()
    group_by_entity = True
    soon_days_raw = (get_setting("SCHEDULE_SOON_DAYS", "7") or "7").strip()
    try:
        soon_days = int(soon_days_raw)
    except ValueError:
        soon_days = 7
    if soon_days < 1:
        soon_days = 7

    soon_limit = today + timedelta(days=soon_days)
    range_7_limit = today + timedelta(days=7)
    range_30_limit = today + timedelta(days=30)
    updated_at = datetime.now()

    with UnitOfWork() as uow:
        documents = (
            uow.session.query(Document)
            .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
            .filter(
                Document.document_type == "invoice",
                Document.is_paid == False,
            )
            .order_by(Document.due_date.asc())
            .all()
        )

    documents = sorted(
        documents,
        key=lambda doc: (doc.due_date is None, doc.due_date or date.max),
    )

    payment_service.attach_payment_amounts(documents)

    schedule_rows = []
    summary = {
        "total": 0,
        "total_amount": 0.0,
        "avg_amount": 0.0,
        "overdue_count": 0,
        "overdue_amount": 0.0,
        "soon_count": 0,
        "soon_amount": 0.0,
        "no_due_count": 0,
    }

    for doc in documents:
        remaining = float(doc.remaining_amount if getattr(doc, "remaining_amount", None) is not None else (doc.total_gross_amount or 0))
        due_status, status_label, status_class = _resolve_due_status(doc.due_date, today, soon_limit)
        due_iso = doc.due_date.strftime("%Y-%m-%d") if doc.due_date else ""
        supplier_name = doc.supplier.name if doc.supplier else "Senza fornitore"
        legal_entity_name = doc.legal_entity.name if doc.legal_entity else "Senza intestatario"
        print_status = (doc.print_status or "not_printed").strip()
        schedule_rows.append(
            {
                "doc": doc,
                "due_status": due_status,
                "status_label": status_label,
                "status_class": status_class,
                "remaining_amount": remaining,
                "remaining_amount_raw": f"{remaining:.2f}",
                "due_iso": due_iso,
                "supplier_name": supplier_name,
                "supplier_id": doc.supplier_id,
                "legal_entity_name": legal_entity_name,
                "legal_entity_id": doc.legal_entity_id,
                "print_status": print_status,
            }
        )

        summary["total"] += 1
        summary["total_amount"] += remaining
        if due_status == "no_due":
            summary["no_due_count"] += 1
        elif due_status == "overdue":
            summary["overdue_count"] += 1
            summary["overdue_amount"] += remaining
        elif due_status == "due_soon":
            summary["soon_count"] += 1
            summary["soon_amount"] += remaining

    if summary["total"]:
        summary["avg_amount"] = summary["total_amount"] / summary["total"]

    status_priority = {"overdue": 0, "due_soon": 1, "scheduled": 2, "no_due": 3}
    schedule_rows.sort(
        key=lambda row: (
            status_priority.get(row["due_status"], 9),
            row["doc"].due_date or date.max,
            -row["remaining_amount"],
            row["doc"].id,
        )
    )

    legal_entity_groups = []
    if group_by_entity:
        group_map = {}
        for row in schedule_rows:
            key = row["legal_entity_id"] if row["legal_entity_id"] is not None else "none"
            if key not in group_map:
                group_map[key] = {
                    "name": row["legal_entity_name"],
                    "legal_entity_id": row["legal_entity_id"],
                    "rows": [],
                    "total_count": 0,
                    "total_amount": 0.0,
                    "overdue_count": 0,
                    "due_soon_count": 0,
                    "scheduled_count": 0,
                    "no_due_count": 0,
                }
            group = group_map[key]
            group["rows"].append(row)
            group["total_count"] += 1
            group["total_amount"] += row["remaining_amount"]
            if row["due_status"] == "overdue":
                group["overdue_count"] += 1
            elif row["due_status"] == "due_soon":
                group["due_soon_count"] += 1
            elif row["due_status"] == "scheduled":
                group["scheduled_count"] += 1
            elif row["due_status"] == "no_due":
                group["no_due_count"] += 1

        legal_entity_groups = list(group_map.values())
        legal_entity_groups.sort(key=lambda group: (group["name"] or "").lower())
        for group in legal_entity_groups:
            group["rows"].sort(
                key=lambda row: (
                    status_priority.get(row["due_status"], 9),
                    row["doc"].due_date or date.max,
                    -row["remaining_amount"],
                    row["doc"].id,
                )
            )

    return render_template(
        "payments/schedule.html",
        schedule_rows=schedule_rows,
        legal_entity_groups=legal_entity_groups,
        summary=summary,
        today=today,
        soon_limit=soon_limit,
        soon_days=soon_days,
        range_7_limit=range_7_limit,
        range_30_limit=range_30_limit,
        updated_at=updated_at,
    )

@payments_bp.route("/schedule/print", methods=["POST"], endpoint="schedule_print")
def schedule_print():
    raw_ids = (request.form.get("document_ids") or "").strip()
    ids = [int(value) for value in raw_ids.split(",") if value.strip().isdigit()]
    if not ids:
        flash("Seleziona almeno un documento.", "warning")
        return redirect(request.referrer or url_for("payments.schedule_view"))

    updated = mark_documents_as_programmed(ids)
    flash(
        f"{updated} documenti segnati come programmati. Stampa PDF non ancora disponibile.",
        "info",
    )
    return redirect(request.referrer or url_for("payments.schedule_view"))

@payments_bp.route("/add/<int:document_id>", methods=["POST"])
def add_view(document_id: int):
    try:
        # Gestione virgola/punto per l'importo
        amount_str = request.form.get("amount", "0").replace(",", ".")
        if not amount_str:
            amount = 0.0
        else:
            amount = float(amount_str)
            
        date_str = request.form.get("payment_date")
        description = request.form.get("description")

        if not date_str:
            flash("Data pagamento obbligatoria.", "warning")
            return redirect(url_for("documents.detail_view", document_id=document_id))

        payment_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        add_payment(
            document_id=document_id,
            amount=amount,
            payment_date=payment_date,
            description=description
        )
        flash("Pagamento aggiunto con successo.", "success")

    except ValueError:
        flash("Importo non valido.", "danger")
    except Exception as e:
        flash(f"Errore durante il salvataggio: {e}", "danger")

    return redirect(url_for("documents.detail_view", document_id=document_id))

@payments_bp.route("/delete/<int:payment_id>", methods=["POST"])
def delete_view(payment_id: int):
    # Recuperiamo document_id prima di cancellare per il redirect 
    # (idealmente il service potrebbe ritornarlo, ma qui usiamo il referrer)
    
    if delete_payment(payment_id):
        flash("Pagamento cancellato.", "success")
    else:
        flash("Errore: pagamento non trovato.", "danger")

    # Torna alla pagina da cui sei venuto (solitamente il dettaglio fattura)
    return redirect(request.referrer or url_for("documents.list_view"))


@payments_bp.route("/batch", methods=["POST"])
def batch_payment():
    """Registra un pagamento cumulativo su più documenti (invoices)."""
    file = request.files.get("file")
    method = request.form.get("method") or request.form.get("payment_method")
    notes = request.form.get("notes")

    # Get selected DOCUMENT IDs (the form sends doc.id as payment_id)
    selected_doc_ids = request.form.getlist("payment_id")

    # Validate input
    if not selected_doc_ids:
        flash("Seleziona almeno un documento da pagare.", "warning")
        return redirect(url_for("payments.payment_index"))

    # Build document allocations from amounts
    doc_allocations = []
    for doc_id in selected_doc_ids:
        raw_amount = (request.form.get(f"amount_{doc_id}") or "0").replace(",", ".")
        try:
            amount = float(raw_amount)
        except ValueError:
            flash(f"Importo non valido per documento {doc_id}", "warning")
            return redirect(url_for("payments.payment_index"))

        if amount <= 0:
            continue

        doc_allocations.append({"document_id": int(doc_id), "amount": amount})

    if not doc_allocations:
        flash("Inserisci almeno un importo > 0.", "warning")
        return redirect(url_for("payments.payment_index"))

    # Process batch payment (service layer handles Document → Payment mapping)
    try:
        result = payment_service.create_batch_payment_from_documents(
            file=file,
            document_allocations=doc_allocations,
            method=method,
            notes=notes
        )

        # Display results
        if result['success_count'] > 0:
            flash(f"{result['success_count']} pagamenti registrati con successo.", "success")

        if result['error_count'] > 0:
            for res in result['results']:
                if not res['success']:
                    flash(f"Errore per documento {res['document_id']}: {res['error']}", "danger")

    except Exception as exc:  # pragma: no cover - logging/flash only
        flash(f"Errore durante il pagamento cumulativo: {exc}", "danger")

    return redirect(url_for("payments.payment_index"))


@payments_bp.route("/ocr", methods=["POST"])
def ocr_view():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"success": False, "error": "File mancante."}), 400

    suffix = Path(file.filename).suffix.lower()
    if not suffix:
        return jsonify({"success": False, "error": "Estensione file mancante."}), 400

    from app.services.settings_service import get_setting
    default_lang = get_setting("OCR_DEFAULT_LANG", "ita")
    lang = (request.form.get("lang") or default_lang).strip() or default_lang
    max_pages = ocr_service.normalize_max_pages(
        request.form.get("max_pages"),
        default=int(get_setting("OCR_MAX_PAGES", "5") or 5),
    )

    try:
        text = ocr_service.extract_text_from_bytes(
            file.read(),
            suffix=suffix,
            lang=lang,
            max_pages=max_pages,
            logger=current_app.logger,
        )
    except ocr_service.OcrDependencyError as exc:
        return jsonify({"success": False, "error": f"OCR non disponibile: {exc}"}), 400
    except ocr_service.OcrError as exc:
        return jsonify({"success": False, "error": f"OCR fallito: {exc}"}), 400

    text = (text or "").strip()
    if not text:
        return jsonify({"success": False, "error": "OCR completato ma nessun testo estratto."}), 200

    return jsonify({"success": True, "text": text})


@payments_bp.route("/ocr-map", methods=["POST"])
def ocr_map_view():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"success": False, "error": "File mancante."}), 400

    suffix = Path(file.filename).suffix.lower()
    if not suffix:
        return jsonify({"success": False, "error": "Estensione file mancante."}), 400

    from app.services.settings_service import get_setting
    default_lang = get_setting("OCR_DEFAULT_LANG", "ita")
    lang = (request.form.get("lang") or default_lang).strip() or default_lang
    max_pages = ocr_service.normalize_max_pages(
        request.form.get("max_pages"),
        default=int(get_setting("OCR_MAX_PAGES", "5") or 5),
    )

    try:
        text = ocr_service.extract_text_from_bytes(
            file.read(),
            suffix=suffix,
            lang=lang,
            max_pages=max_pages,
            logger=current_app.logger,
        )
    except ocr_service.OcrDependencyError as exc:
        return jsonify({"success": False, "error": f"OCR non disponibile: {exc}"}), 400
    except ocr_service.OcrError as exc:
        return jsonify({"success": False, "error": f"OCR fallito: {exc}"}), 400

    text = (text or "").strip()
    if not text:
        return jsonify({"success": False, "error": "OCR completato ma nessun testo estratto."}), 200

    fields = parse_payment_fields(text)
    return jsonify({"success": True, "text": text, "fields": fields})


@payments_bp.route("/history/<int:payment_id>", methods=["GET"], endpoint="payment_detail_view")
def payment_detail_view(payment_id: int):
    """
    Mostra il dettaglio di un pagamento e dei documenti collegati.
    """
    detail = get_payment_event_detail(payment_id)
    if not detail:
        flash("Pagamento non trovato.", "warning")
        return redirect(url_for("payments.payment_index") + "#tab-history")

    payment_document = detail.get("payment_document")
    has_payment_file = False
    if payment_document and payment_document.file_path:
        base_path = settings_service.get_payment_files_storage_path()
        full_path = settings_service.resolve_storage_path(base_path, payment_document.file_path)
        has_payment_file = os.path.exists(full_path)
    detail["has_payment_file"] = has_payment_file

    return render_template("payments/detail.html", **detail)


@payments_bp.route("/history/<int:payment_id>/file", methods=["GET"], endpoint="payment_file_view")
def payment_file_view(payment_id: int):
    detail = get_payment_event_detail(payment_id)
    if not detail:
        flash("Pagamento non trovato.", "warning")
        return redirect(url_for("payments.payment_index") + "#tab-history")

    payment_document = detail.get("payment_document")
    if not payment_document or not payment_document.file_path:
        flash("Nessun file collegato a questo pagamento.", "warning")
        return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))

    base_path = settings_service.get_payment_files_storage_path()
    full_path = settings_service.resolve_storage_path(base_path, payment_document.file_path)
    if not os.path.exists(full_path):
        flash("File pagamento non trovato su disco.", "danger")
        return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))

    return send_file(full_path, as_attachment=False)


@payments_bp.route("/history/<int:payment_id>/file", methods=["POST"], endpoint="payment_file_upload")
def payment_file_upload(payment_id: int):
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Seleziona un PDF da caricare.", "warning")
        return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))

    if not _is_allowed_payment_file(file.filename):
        flash("Formato file non supportato. Usa PDF.", "danger")
        return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))

    try:
        attach_payment_document_file(payment_id, file)
        flash("File pagamento aggiornato.", "success")
    except ValueError as exc:
        flash(str(exc), "warning")
    except Exception as exc:
        flash(f"Errore durante il caricamento: {exc}", "danger")

    return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))
