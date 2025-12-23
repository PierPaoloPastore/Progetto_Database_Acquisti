"""
API JSON per i documenti (Document).

Endpoint principali:

POST /api/documents/<document_id>/status
    Aggiorna stato documento e data scadenza.

POST /api/documents/lines/<line_id>/category
    Assegna (o rimuove) una categoria a una singola riga.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask import Blueprint, request, jsonify

# Importiamo i servizi aggiornati
from app.services import update_document_status
from app.services import assign_category_to_line
from app.models import DocumentLine

# Rinomina Blueprint
api_documents_bp = Blueprint("api_documents", __name__)


def _parse_date(value: str) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@api_documents_bp.route("/<int:document_id>/status", methods=["POST"])
def api_update_document_status(document_id: int):
    """
    Aggiorna lo stato di un documento.

    Body JSON atteso:
    {
      "doc_status": "pending_physical_copy|verified|archived",
      "due_date": "YYYY-MM-DD"  (opzionale)
    }
    """
    data = request.get_json(silent=True) or {}
    doc_status = data.get("doc_status")
    # payment_status ignorato perché deprecato in v3 (gestito da Payment)
    due_date_str = data.get("due_date")
    due_date = _parse_date(due_date_str) if due_date_str else None

    document = update_document_status(
        document_id=document_id,
        doc_status=doc_status,
        due_date=due_date,
    )

    if document is None:
        return jsonify(
            {
                "success": False,
                "message": "Documento non trovato o errore di aggiornamento.",
                "payload": None,
            }
        ), 404

    return jsonify(
        {
            "success": True,
            "message": "Stato documento aggiornato con successo.",
            "payload": {
                "document_id": document.id,
                "doc_status": document.doc_status,
                "due_date": document.due_date.isoformat() if document.due_date else None,
            },
        }
    )


@api_documents_bp.route("/lines/<int:line_id>/category", methods=["POST"])
def api_assign_category_to_line(line_id: int):
    """
    Assegna o rimuove una categoria a una singola riga.
    (Questa route rimane invariata nella logica, cambia solo il prefisso URL)
    """
    data = request.get_json(silent=True) or {}
    category_id = data.get("category_id", None)

    if category_id is not None:
        try:
            category_id = int(category_id)
        except (TypeError, ValueError):
            return jsonify(
                {
                    "success": False,
                    "message": "category_id non valido.",
                    "payload": None,
                }
            ), 400

    line: Optional[DocumentLine] = assign_category_to_line(
        line_id=line_id,
        category_id=category_id,
    )

    if line is None:
        return jsonify(
            {
                "success": False,
                "message": "Riga non trovata o categoria inesistente.",
                "payload": None,
            }
        ), 404

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
