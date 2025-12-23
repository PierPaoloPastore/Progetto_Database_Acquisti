"""
Route per la gestione delle Bolle / DDT (DeliveryNote).
"""
from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app

from app.services import (
    list_delivery_notes,
    create_delivery_note,
    get_delivery_note,
    get_delivery_note_file_path,
    get_delivery_note_with_lines,
    upsert_delivery_note_lines,
    link_delivery_note_to_document,
    ocr_service,
)
from app.services.supplier_service import list_active_suppliers
from app.services.document_service import search_documents
from app.repositories.legal_entity_repo import list_legal_entities


delivery_notes_bp = Blueprint("delivery_notes", __name__)


@delivery_notes_bp.route("/", methods=["GET"])
def list_view():
    search_term = (request.args.get("q") or "").strip() or None
    supplier_id = request.args.get("supplier_id")
    supplier_id = int(supplier_id) if supplier_id else None
    legal_entity_id = request.args.get("legal_entity_id")
    legal_entity_id = int(legal_entity_id) if legal_entity_id else None

    notes = list_delivery_notes(
        search_term=search_term,
        supplier_id=supplier_id,
        legal_entity_id=legal_entity_id,
        status=None,
        limit=200,
    )

    suppliers = list_active_suppliers()
    legal_entities = list_legal_entities(include_inactive=False)

    return render_template(
        "delivery_notes/list.html",
        delivery_notes=notes,
        suppliers=suppliers,
        legal_entities=legal_entities,
        search_term=search_term or "",
        selected_supplier_id=supplier_id,
        selected_legal_entity_id=legal_entity_id,
    )


@delivery_notes_bp.route("/", methods=["POST"])
def create_view():
    try:
        supplier_id = int(request.form.get("supplier_id") or 0)
        legal_entity_id_raw = request.form.get("legal_entity_id")
        legal_entity_id = int(legal_entity_id_raw) if legal_entity_id_raw else None
        ddt_number = (request.form.get("ddt_number") or "").strip()
        ddt_date_str = request.form.get("ddt_date")
        total_amount_raw = request.form.get("total_amount") or None
        total_amount = Decimal(total_amount_raw.replace(",", ".")) if total_amount_raw else None
        file = request.files.get("file")

        if not ddt_date_str:
            raise ValueError("Data DDT obbligatoria")
        ddt_date = datetime.strptime(ddt_date_str, "%Y-%m-%d").date()

        note = create_delivery_note(
            supplier_id=supplier_id,
            legal_entity_id=legal_entity_id,
            ddt_number=ddt_number,
            ddt_date=ddt_date,
            total_amount=total_amount,
            file=file,
            source="pdf_import",
            status="unmatched",
        )

        flash(f"DDT #{note.ddt_number} registrato con successo.", "success")
        return redirect(url_for("delivery_notes.detail_view", delivery_note_id=note.id))
    except Exception as exc:
        flash(f"Errore salvataggio DDT: {exc}", "danger")
        return redirect(url_for("delivery_notes.list_view"))


@delivery_notes_bp.route("/ocr", methods=["POST"])
def ocr_view():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"success": False, "error": "File mancante."}), 400

    suffix = Path(file.filename).suffix.lower()
    if not suffix:
        return jsonify({"success": False, "error": "Estensione file mancante."}), 400

    lang = (request.form.get("lang") or "ita").strip() or "ita"
    max_pages = ocr_service.normalize_max_pages(request.form.get("max_pages"))

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


@delivery_notes_bp.route("/<int:delivery_note_id>/file", methods=["GET"])
def file_view(delivery_note_id: int):
    note = get_delivery_note(delivery_note_id)
    if not note:
        flash("DDT non trovato.", "warning")
        return redirect(url_for("delivery_notes.list_view"))

    full_path = get_delivery_note_file_path(note)
    if not full_path or not os.path.exists(full_path):
        flash("File DDT non trovato su disco.", "danger")
        return redirect(url_for("delivery_notes.list_view"))

    return send_file(full_path, as_attachment=False)


@delivery_notes_bp.route("/<int:delivery_note_id>", methods=["GET", "POST"])
def detail_view(delivery_note_id: int):
    note = get_delivery_note_with_lines(delivery_note_id)
    if not note:
        flash("DDT non trovato.", "warning")
        return redirect(url_for("delivery_notes.list_view"))

    if request.method == "POST":
        # Collect lines from form arrays
        ids = request.form.getlist("line_id")
        numbers = request.form.getlist("line_number")
        descriptions = request.form.getlist("description")
        item_codes = request.form.getlist("item_code")
        quantities = request.form.getlist("quantity")
        uoms = request.form.getlist("uom")
        amounts = request.form.getlist("amount")
        notes_list = request.form.getlist("notes")

        payload = []
        for idx in range(len(numbers)):
            payload.append(
                {
                    "id": ids[idx] or None,
                    "line_number": numbers[idx],
                    "description": descriptions[idx],
                    "item_code": item_codes[idx] if idx < len(item_codes) else None,
                    "quantity": quantities[idx] if idx < len(quantities) else None,
                    "uom": uoms[idx] if idx < len(uoms) else None,
                    "amount": amounts[idx] if idx < len(amounts) else None,
                    "notes": notes_list[idx] if idx < len(notes_list) else None,
                }
            )
        try:
            upsert_delivery_note_lines(delivery_note_id, payload)
            flash("Righe DDT salvate.", "success")
            return redirect(url_for("delivery_notes.detail_view", delivery_note_id=delivery_note_id))
        except Exception as exc:
            flash(f"Errore salvataggio righe: {exc}", "danger")

    return render_template(
        "delivery_notes/detail.html",
        note=note,
    )


@delivery_notes_bp.route("/<int:delivery_note_id>/match-document", methods=["GET", "POST"])
def match_document_view(delivery_note_id: int):
    note = get_delivery_note(delivery_note_id)
    if not note:
        flash("DDT non trovato.", "warning")
        return redirect(url_for("delivery_notes.list_view"))

    if request.method == "POST":
        document_id = request.form.get("document_id")
        status = request.form.get("status") or "matched"
        if not document_id:
            flash("Seleziona una fattura da abbinare.", "warning")
            return redirect(url_for("delivery_notes.match_document_view", delivery_note_id=delivery_note_id))
        try:
            link_delivery_note_to_document(delivery_note_id, int(document_id), status=status)
            flash("Fattura abbinata al DDT.", "success")
            return redirect(url_for("delivery_notes.detail_view", delivery_note_id=delivery_note_id))
        except Exception as exc:
            flash(f"Errore in abbinamento fattura: {exc}", "danger")

    documents = []
    if note and note.supplier_id:
        # cerca documenti del fornitore (limite 200)
        from app.services.dto import DocumentSearchFilters
        filters = DocumentSearchFilters.from_query_args({})
        filters.supplier_id = note.supplier_id
        documents = search_documents(filters=filters, limit=200, document_type=None)

    return render_template(
        "delivery_notes/match_document.html",
        note=note,
        documents=documents,
    )
