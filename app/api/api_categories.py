"""
API JSON per le categorie (Category).

Endpoint principali:

GET  /api/categories/
    Restituisce l'elenco delle categorie attive (id, name, description).

POST /api/categories/bulk-assign
    Assegna (o rimuove) una categoria a un insieme di righe di una fattura.
"""

from __future__ import annotations

from typing import List, Optional

from flask import Blueprint, request, jsonify

from app.services import (
    list_categories_for_ui,
    bulk_assign_category_to_invoice_lines,
)

api_categories_bp = Blueprint("api_categories", __name__)


@api_categories_bp.route("/", methods=["GET"])
def api_list_categories():
    """
    Restituisce l'elenco delle categorie attive, pensato per JS.

    Output:
    {
      "success": true,
      "message": "",
      "payload": [
        {
          "id": ...,
          "name": "...",
          "description": "...",
        },
        ...
      ]
    }
    """
    categories = list_categories_for_ui()

    payload = [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
        }
        for c in categories
    ]

    return jsonify(
        {
            "success": True,
            "message": "",
            "payload": payload,
        }
    )


@api_categories_bp.route("/bulk-assign", methods=["POST"])
def api_bulk_assign_category():
    """
    Assegna (o rimuove) una categoria alle righe di una fattura.

    Body JSON atteso:
    {
      "invoice_id": 123,
      "category_id": 45,        # oppure null per rimuovere categoria
      "line_ids": [1, 2, 3]     # opzionale; se assente -> tutte le righe
    }
    """
    data = request.get_json(silent=True) or {}

    invoice_id = data.get("invoice_id")
    category_id = data.get("category_id", None)
    line_ids = data.get("line_ids", None)

    # Validazione minima
    try:
        invoice_id = int(invoice_id)
    except (TypeError, ValueError):
        return jsonify(
            {
                "success": False,
                "message": "invoice_id mancante o non valido.",
                "payload": None,
            }
        ), 400

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

    normalized_line_ids: Optional[List[int]] = None
    if isinstance(line_ids, list):
        temp: List[int] = []
        for v in line_ids:
            try:
                temp.append(int(v))
            except (TypeError, ValueError):
                continue
        normalized_line_ids = temp if temp else None

    result = bulk_assign_category_to_invoice_lines(
        invoice_id=invoice_id,
        category_id=category_id,
        line_ids=normalized_line_ids,
    )

    status_code = 200 if result.get("success") else 400

    return jsonify(
        {
            "success": bool(result.get("success")),
            "message": result.get("message", ""),
            "payload": {
                "updated_count": result.get("updated_count", 0),
            },
        }
    ), status_code
