"""
API JSON per le fatture (Invoice -> Document).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask import Blueprint, request, jsonify

# FIX: Importa la funzione corretta dal nuovo service
from app.services import update_document_status
from app.services import assign_category_to_line
from app.models import InvoiceLine

api_invoices_bp = Blueprint("api_invoices", __name__)


def _parse_date(value: str) -> Optional[datetime.date]:
    if not value: return None
    try: return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError: return None


@api_invoices_bp.route("/<int:invoice_id>/status", methods=["POST"])
def api_update_invoice_status(invoice_id: int):
    """
    Aggiorna lo stato di un documento.
    """
    data = request.get_json(silent=True) or {}
    doc_status = data.get("doc_status")
    payment_status = data.get("payment_status")
    due_date_str = data.get("due_date")
    due_date = _parse_date(due_date_str) if due_date_str else None

    # Usa update_document_status
    document = update_document_status(
        document_id=invoice_id,
        doc_status=doc_status,
        payment_status=payment_status,
        due_date=due_date,
    )

    if document is None:
        return jsonify(
            {
                "success": False,
                "message": "Fattura non trovata o errore di aggiornamento.",
                "payload": None,
            }
        ), 404

    return jsonify(
        {
            "success": True,
            "message": "Stato fattura aggiornato con successo.",
            "payload": {
                "invoice_id": document.id,
                "doc_status": document.doc_status,
                "due_date": document.due_date.isoformat() if document.due_date else None,
            },
        }
    )


@api_invoices_bp.route("/lines/<int:line_id>/category", methods=["POST"])
def api_assign_category_to_line(line_id: int):
    """Assegna o rimuove una categoria a una riga."""
    data = request.get_json(silent=True) or {}
    category_id = data.get("category_id", None)

    if category_id is not None:
        try: category_id = int(category_id)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "category_id non valido.", "payload": None}), 400

    line: Optional[InvoiceLine] = assign_category_to_line(
        line_id=line_id,
        category_id=category_id,
    )

    if line is None:
        return jsonify({"success": False, "message": "Riga non trovata.", "payload": None}), 404

    return jsonify(
        {
            "success": True,
            "message": "Categoria aggiornata con successo.",
            "payload": {
                "line_id": line.id,
                "document_id": line.document_id,
                "category_id": line.category_id,
            },
        }
    )