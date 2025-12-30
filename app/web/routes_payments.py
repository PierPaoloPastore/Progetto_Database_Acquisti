"""
Route per la gestione dei Pagamenti.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from pathlib import Path
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify, current_app
from sqlalchemy.orm import joinedload

from app.models import Document
from app.services import payment_service, ocr_service
from app.services.settings_service import get_setting
from app.services.ocr_mapping_service import parse_payment_fields
from app.services.payment_service import (
    add_payment,
    create_batch_payment,
    delete_payment,
    get_payment_event_detail,
    list_paid_payments,
    list_payments_by_document,
)
from app.services.unit_of_work import UnitOfWork

payments_bp = Blueprint("payments", __name__)

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
    soon_days_raw = (get_setting("SCHEDULE_SOON_DAYS", "7") or "7").strip()
    try:
        soon_days = int(soon_days_raw)
    except ValueError:
        soon_days = 7
    if soon_days < 1:
        soon_days = 7

    soon_limit = today + timedelta(days=soon_days)

    with UnitOfWork() as uow:
        documents = (
            uow.session.query(Document)
            .options(joinedload(Document.supplier))
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

    summary = {
        "total": 0,
        "total_amount": 0.0,
        "overdue_count": 0,
        "overdue_amount": 0.0,
        "soon_count": 0,
        "soon_amount": 0.0,
        "no_due_count": 0,
    }

    for doc in documents:
        summary["total"] += 1
        remaining = float(doc.remaining_amount if getattr(doc, "remaining_amount", None) is not None else (doc.total_gross_amount or 0))
        summary["total_amount"] += remaining

        if doc.due_date is None:
            summary["no_due_count"] += 1
        elif doc.due_date < today:
            summary["overdue_count"] += 1
            summary["overdue_amount"] += remaining
        elif doc.due_date <= soon_limit:
            summary["soon_count"] += 1
            summary["soon_amount"] += remaining

    return render_template(
        "payments/schedule.html",
        documents=documents,
        summary=summary,
        today=today,
        soon_limit=soon_limit,
        soon_days=soon_days,
    )

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

    return render_template("payments/detail.html", **detail)
