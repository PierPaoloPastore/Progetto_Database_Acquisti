"""
Route per la gestione dei Pagamenti.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
import io
from math import ceil
import os
from pathlib import Path
from flask import Blueprint, request, redirect, url_for, flash, render_template, jsonify, current_app, send_file
from sqlalchemy.orm import joinedload

from app.models import Document
from app.services import payment_service, ocr_service, settings_service, list_all_bank_accounts
from app.services.document_service import mark_documents_as_programmed, unmark_documents_as_programmed
from app.services.pdf_service import render_pdf_from_html
from app.services.settings_service import get_setting
from app.services.ocr_mapping_service import parse_payment_fields
from app.services.payment_method_catalog import (
    get_payment_method_label,
    list_payment_method_choices,
    normalize_payment_method_code,
)
from app.services.dto import PaymentHistoryFilters
from app.services.payment_service import (
    add_payment,
    delete_payment,
    attach_payment_document_file,
    get_payment_event_detail,
    list_paid_payments_page,
    update_payment,
)
from app.services.unit_of_work import UnitOfWork

payments_bp = Blueprint("payments", __name__)

_ALLOWED_PAYMENT_EXTENSIONS = {".pdf"}
_PAYMENT_HISTORY_PAGE_SIZE = 50
_UNPAID_INVOICES_PAGE_SIZE = 100


def _is_allowed_payment_file(filename: str) -> bool:
    suffix = Path(filename).suffix.lower()
    return suffix in _ALLOWED_PAYMENT_EXTENSIONS


def _parse_positive_int(value: str | None, default: int = 1) -> int:
    try:
        parsed = int(value or "")
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _parse_document_ids_arg(*values: str | None) -> list[int]:
    parsed_ids: list[int] = []
    seen: set[int] = set()
    for raw_value in values:
        if not raw_value:
            continue
        for token in str(raw_value).split(","):
            token = token.strip()
            if not token.isdigit():
                continue
            doc_id = int(token)
            if doc_id in seen:
                continue
            seen.add(doc_id)
            parsed_ids.append(doc_id)
    return parsed_ids


def _build_pagination(
    *,
    total: int,
    page: int,
    page_size: int,
    make_url,
) -> dict:
    total_pages = max(1, ceil(total / page_size)) if total else 1
    current_page = min(max(page, 1), total_pages)
    start_item = ((current_page - 1) * page_size + 1) if total else 0
    end_item = min(current_page * page_size, total) if total else 0
    window_start = max(1, current_page - 2)
    window_end = min(total_pages, current_page + 2)
    pages = [
        {
            "number": page_number,
            "url": make_url(page_number),
            "active": page_number == current_page,
        }
        for page_number in range(window_start, window_end + 1)
    ]
    return {
        "page": current_page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "start_item": start_item,
        "end_item": end_item,
        "has_prev": current_page > 1,
        "has_next": current_page < total_pages,
        "prev_url": make_url(current_page - 1) if current_page > 1 else None,
        "next_url": make_url(current_page + 1) if current_page < total_pages else None,
        "pages": pages,
    }

def _resolve_due_status(due_date: date | None, today: date, soon_limit: date) -> tuple[str, str, str]:
    if due_date is None:
        return "no_due", "Senza scadenza", "secondary"
    if due_date < today:
        return "overdue", "Scaduta", "danger"
    if due_date <= soon_limit:
        return "due_soon", "In scadenza", "warning"
    return "scheduled", "Non scaduta", "info"


def _build_schedule_rows(documents, today: date, soon_limit: date):
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
        remaining = float(
            doc.remaining_amount
            if getattr(doc, "remaining_amount", None) is not None
            else (doc.total_gross_amount or 0)
        )
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

    return schedule_rows, summary

@payments_bp.route("/", methods=["GET"], endpoint="payment_index")
def payment_index():
    """
    Mostra la dashboard dei pagamenti.
    """
    payment_history_filters = PaymentHistoryFilters.from_query_args(request.args)
    history_page = _parse_positive_int(request.args.get("history_page"), default=1)
    invoice_page = _parse_positive_int(request.args.get("invoice_page"), default=1)
    preset_document_ids = _parse_document_ids_arg(
        request.args.get("document_id"),
        request.args.get("document_ids"),
    )
    preset_amount_raw = (request.args.get("amount") or "").strip()
    preset_amounts: dict[int, str] = {}
    if preset_document_ids and preset_amount_raw:
        preset_amounts[preset_document_ids[0]] = preset_amount_raw

    payment_history, payment_history_total, history_page = list_paid_payments_page(
        filters=payment_history_filters,
        page=history_page,
        page_size=_PAYMENT_HISTORY_PAGE_SIZE,
    )
    payment_method_choices = list_payment_method_choices()
    payment_method_labels = {
        code: get_payment_method_label(code) or code for code, _ in payment_method_choices
    }

    with UnitOfWork() as uow:
        all_unpaid_invoices, unpaid_invoices_total, invoice_page = (
            uow.documents.list_unpaid_invoices_page(
                page=invoice_page,
                page_size=_UNPAID_INVOICES_PAGE_SIZE,
            )
        )
        if preset_document_ids:
            preset_documents = (
                uow.session.query(Document)
                .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
                .filter(
                    Document.id.in_(preset_document_ids),
                    Document.document_type == "invoice",
                    Document.is_paid == False,
                )
                .all()
            )
            existing_ids = {doc.id for doc in all_unpaid_invoices}
            preset_docs_by_id = {doc.id: doc for doc in preset_documents}
            missing_preset_documents = [
                preset_docs_by_id[doc_id]
                for doc_id in preset_document_ids
                if doc_id in preset_docs_by_id and doc_id not in existing_ids
            ]
            if missing_preset_documents:
                all_unpaid_invoices = missing_preset_documents + all_unpaid_invoices

    payment_service.attach_payment_amounts(all_unpaid_invoices)
    bank_accounts = list_all_bank_accounts()
    history_base_params = {
        **payment_history_filters.to_query_params(),
        "tab": "tab-history",
        "invoice_page": invoice_page,
    }
    invoice_base_params = {
        **payment_history_filters.to_query_params(),
        "tab": "tab-new",
        "history_page": history_page,
    }
    history_pagination = _build_pagination(
        total=payment_history_total,
        page=history_page,
        page_size=_PAYMENT_HISTORY_PAGE_SIZE,
        make_url=lambda page_number: url_for(
            "payments.payment_index",
            **history_base_params,
            history_page=page_number,
        ),
    )
    invoice_pagination = _build_pagination(
        total=unpaid_invoices_total,
        page=invoice_page,
        page_size=_UNPAID_INVOICES_PAGE_SIZE,
        make_url=lambda page_number: url_for(
            "payments.payment_index",
            **invoice_base_params,
            invoice_page=page_number,
        ),
    )

    return render_template(
        "payments/index.html",
        all_unpaid_invoices=all_unpaid_invoices,
        payment_history=payment_history,
        bank_accounts=bank_accounts,
        payment_method_choices=payment_method_choices,
        payment_method_labels=payment_method_labels,
        payment_history_filters=payment_history_filters,
        has_payment_history_advanced_filters=payment_history_filters.has_advanced_filters,
        has_payment_history_filters=payment_history_filters.has_filters,
        payment_history_total=payment_history_total,
        payment_history_pagination=history_pagination,
        unpaid_invoices_total=unpaid_invoices_total,
        invoice_pagination=invoice_pagination,
        preset_document_ids=preset_document_ids,
        preset_amounts=preset_amounts,
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
    schedule_rows, summary = _build_schedule_rows(documents, today, soon_limit)

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
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    raw_ids = (request.form.get("document_ids") or "").strip()
    ids = [int(value) for value in raw_ids.split(",") if value.strip().isdigit()]
    if not ids:
        if is_ajax:
            return jsonify({"ok": False, "message": "Seleziona almeno un documento."}), 400
        flash("Seleziona almeno un documento.", "warning")
        return redirect(request.referrer or url_for("payments.schedule_view"))

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
            .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
            .filter(
                Document.document_type == "invoice",
                Document.is_paid == False,
                Document.id.in_(ids),
            )
            .all()
        )

    if not documents:
        if is_ajax:
            return jsonify({"ok": False, "message": "Nessun documento valido da stampare."}), 400
        flash("Nessun documento valido da stampare.", "warning")
        return redirect(request.referrer or url_for("payments.schedule_view"))

    payment_service.attach_payment_amounts(documents)
    schedule_rows, summary = _build_schedule_rows(documents, today, soon_limit)

    status_priority = {"overdue": 0, "due_soon": 1, "scheduled": 2, "no_due": 3}
    schedule_rows.sort(
        key=lambda row: (
            status_priority.get(row["due_status"], 9),
            row["doc"].due_date or date.max,
            -row["remaining_amount"],
            row["doc"].id,
        )
    )

    updated_at = datetime.now()
    html_content = render_template(
        "payments/schedule_print.html",
        schedule_rows=schedule_rows,
        summary=summary,
        today=today,
        updated_at=updated_at,
        soon_days=soon_days,
    )
    base_dir = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    pdf_bytes = render_pdf_from_html(
        html_content,
        base_dir,
        current_app.logger,
        orientation="Landscape",
    )
    if not pdf_bytes:
        if is_ajax:
            return jsonify({"ok": False, "message": "Stampa PDF non disponibile: installa wkhtmltopdf o WeasyPrint."}), 501
        flash("Stampa PDF non disponibile: installa wkhtmltopdf o WeasyPrint.", "warning")
        return redirect(request.referrer or url_for("payments.schedule_view"))

    doc_ids = [row["doc"].id for row in schedule_rows]
    mark_documents_as_programmed(doc_ids)

    download_name = f"scadenziario_{today.isoformat()}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
    )


@payments_bp.route("/schedule/unprogram", methods=["POST"], endpoint="schedule_unprogram")
def schedule_unprogram():
    raw_ids = (request.form.get("document_ids") or "").strip()
    ids = [int(value) for value in raw_ids.split(",") if value.strip().isdigit()]
    if not ids:
        return jsonify({"ok": False, "message": "Seleziona almeno un documento."}), 400

    updated = unmark_documents_as_programmed(ids)
    return jsonify(
        {
            "ok": True,
            "message": f"Flag 'Programmata' rimosso da {updated} documenti.",
            "updated_count": updated,
        }
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
    
    confirm_text = (request.form.get("confirm_text") or "").strip()
    expected = f"Pagamento #{payment_id}"
    if confirm_text.lower() != expected.lower():
        flash("Conferma non valida. Eliminazione annullata.", "warning")
        return redirect(request.referrer or url_for("payments.payment_detail_view", payment_id=payment_id))

    if delete_payment(payment_id):
        flash("Pagamento cancellato.", "success")
    else:
        flash("Errore: pagamento non trovato.", "danger")

    # Torna alla pagina da cui sei venuto (solitamente il dettaglio fattura)
    return redirect(request.referrer or url_for("documents.list_view"))


@payments_bp.route("/history/<int:payment_id>/edit", methods=["POST"])
def edit_payment_view(payment_id: int):
    confirm_text = (request.form.get("confirm_text") or "").strip()
    expected = f"Pagamento #{payment_id}"
    if confirm_text.lower() != expected.lower():
        flash("Conferma non valida. Modifica annullata.", "warning")
        return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))

    paid_date = None
    date_str = (request.form.get("paid_date") or "").strip()
    if date_str:
        try:
            paid_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Data pagamento non valida.", "warning")
            return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))

    paid_amount = (request.form.get("paid_amount") or "").replace(",", ".")
    if paid_amount == "":
        paid_amount_value = None
    else:
        try:
            paid_amount_value = float(paid_amount)
        except ValueError:
            flash("Importo non valido.", "warning")
            return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))

    ok, message = update_payment(
        payment_id,
        paid_date=paid_date,
        paid_amount=paid_amount_value,
        payment_method=request.form.get("payment_method") or None,
        notes=request.form.get("notes") or None,
    )
    flash(message, "success" if ok else "danger")
    return redirect(url_for("payments.payment_detail_view", payment_id=payment_id))


@payments_bp.route("/batch", methods=["POST"])
def batch_payment():
    """Registra un pagamento cumulativo su più documenti (invoices)."""
    file = request.files.get("file")
    method = request.form.get("method") or request.form.get("payment_method")
    method = normalize_payment_method_code(method) if method else None
    notes = request.form.get("notes")
    bank_account_iban = request.form.get("bank_account_iban")
    payment_date = None
    date_str = (request.form.get("payment_date") or "").strip()
    if date_str:
        try:
            payment_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Data pagamento non valida.", "warning")
            return redirect(url_for("payments.payment_index"))

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
            notes=notes,
            bank_account_iban=bank_account_iban,
            payment_date=payment_date,
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
    payment = detail.get("payment")
    method_label = None
    if payment and payment.payment_method:
        method_label = get_payment_method_label(payment.payment_method) or payment.payment_method
    if not method_label and payment_document and payment_document.payment_type:
        method_label = payment_document.payment_type
    detail["payment_method_label"] = method_label
    detail["payment_confirm_label"] = f"Pagamento #{payment_id}"
    detail["payment_method_choices"] = list_payment_method_choices()
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
