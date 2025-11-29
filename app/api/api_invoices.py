"""
API JSON per le fatture (Invoice).

Endpoint principali:

POST /api/invoices/<invoice_id>/status
    Aggiorna stato documento/pagamento e data scadenza.

POST /api/invoices/lines/<line_id>/category
    Assegna (o rimuove) una categoria a una singola riga fattura.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask import Blueprint, request, jsonify

from app.services import update_invoice_status
from app.services import assign_category_to_line  # via category_service
from app.models import InvoiceLine

api_invoices_bp = Blueprint("api_invoices", __name__)


def _parse_date(value: str) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@api_invoices_bp.route("/<int:invoice_id>/status", methods=["POST"])
def api_update_invoice_status(invoice_id: int):
    """
    Aggiorna lo stato di una fattura.

    Body JSON atteso:
    {
      "doc_status": "imported|pending_physical_copy|verified|rejected|archived",
         # imported: appena importata
         # pending_physical_copy: in attesa di copia cartacea
         # verified: controllata e pronta all'uso
         # rejected: scartata dopo verifica
         # archived: chiusa/archiviata
      "payment_status": "unpaid|partial|paid|...",
      "due_date": "YYYY-MM-DD"  (opzionale)
    }
    """
    data = request.get_json(silent=True) or {}
    doc_status = data.get("doc_status")
    payment_status = data.get("payment_status")
    due_date_str = data.get("due_date")
    due_date = _parse_date(due_date_str) if due_date_str else None

    invoice = update_invoice_status(
        invoice_id=invoice_id,
        doc_status=doc_status,
        payment_status=payment_status,
        due_date=due_date,
    )

    if invoice is None:
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
                "invoice_id": invoice.id,
                "doc_status": invoice.doc_status,
                "payment_status": invoice.payment_status,
                "due_date": invoice.due_date.isoformat()
                if invoice.due_date
                else None,
            },
        }
    )


@api_invoices_bp.route("/lines/<int:line_id>/category", methods=["POST"])
def api_assign_category_to_line(line_id: int):
    """
    Assegna o rimuove una categoria a una singola riga fattura.

    Body JSON atteso:
    {
      "category_id": 123   # oppure null per rimuovere
    }
    """
    data = request.get_json(silent=True) or {}
    category_id = data.get("category_id", None)

    if category_id is not None:
        # Provo a convertirlo a int; se fallisce consideriamo il campo non valido
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

    line: Optional[InvoiceLine] = assign_category_to_line(
        line_id=line_id,
        category_id=category_id,
    )

    if line is None:
        return jsonify(
            {
                "success": False,
                "message": "Riga fattura non trovata o categoria inesistente.",
                "payload": None,
            }
        ), 404

    return jsonify(
        {
            "success": True,
            "message": "Categoria aggiornata con successo.",
            "payload": {
                "line_id": line.id,
                "invoice_id": line.invoice_id,
                "category_id": line.category_id,
            },
        }
    )
