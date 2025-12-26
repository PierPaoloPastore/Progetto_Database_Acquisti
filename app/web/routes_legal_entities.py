"""
Route per la gestione delle intestazioni (LegalEntity).

Comprende:
- elenco intestazioni con statistiche base (GET /legal-entities/)
- dettaglio intestazione con elenco documenti (GET /legal-entities/<id>)
"""
from __future__ import annotations

from flask import Blueprint, render_template, redirect, request, url_for, flash

from app.services.legal_entity_service import (
    list_legal_entities_with_stats,
    get_legal_entity_detail,
    update_legal_entity,
)

legal_entities_bp = Blueprint("legal_entities", __name__)


@legal_entities_bp.route("/", methods=["GET"])
def list_view():
    """
    Pagina elenco intestazioni.

    Mostra:
    - dati intestazione
    - numero documenti
    - totale importi
    """
    search_term = request.args.get("q") or None
    legal_entities_stats = list_legal_entities_with_stats(search_term=search_term)
    return render_template(
        "legal_entities/list.html",
        legal_entities_stats=legal_entities_stats,
        search_term=search_term or "",
    )


@legal_entities_bp.route("/<int:legal_entity_id>", methods=["GET"])
def detail_view(legal_entity_id: int):
    """
    Pagina dettaglio intestazione.

    Mostra:
    - anagrafica
    - elenco documenti collegati
    """
    raw_supplier_id = request.args.get("supplier_id")
    if not raw_supplier_id:
        selected_supplier_id = None
    else:
        try:
            selected_supplier_id = int(raw_supplier_id)
        except ValueError:
            selected_supplier_id = None

    detail = get_legal_entity_detail(
        legal_entity_id=legal_entity_id,
        supplier_id=selected_supplier_id,
    )
    if detail is None:
        flash("Intestazione non trovata.", "warning")
        return redirect(url_for("legal_entities.list_view"))

    detail["suppliers"] = detail.get(
        "available_suppliers", detail.get("suppliers", [])
    )
    detail["selected_supplier_id"] = selected_supplier_id

    return render_template(
        "legal_entities/detail.html",
        **detail,
    )


@legal_entities_bp.route("/<int:legal_entity_id>/edit", methods=["POST"])
def edit_view(legal_entity_id: int):
    data = request.form
    entity = update_legal_entity(
        legal_entity_id=legal_entity_id,
        name=data.get("name"),
        vat_number=data.get("vat_number"),
        fiscal_code=data.get("fiscal_code"),
        address=data.get("address"),
        city=data.get("city"),
        country=data.get("country"),
        is_active=data.get("is_active"),
    )
    if entity is None:
        flash("Intestazione non trovata.", "warning")
    else:
        flash("Intestazione aggiornata.", "success")
    return redirect(url_for("legal_entities.detail_view", legal_entity_id=legal_entity_id))
