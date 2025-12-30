"""
Route per la gestione dei fornitori (Supplier).

Comprende:
- elenco fornitori con statistiche base (GET /suppliers/)
- dettaglio fornitore con elenco fatture (GET /suppliers/<id>)
"""

from __future__ import annotations

from flask import Blueprint, render_template, redirect, request, url_for, flash

from app.services import (
    list_suppliers_with_stats,
    get_supplier_detail,
    update_supplier,
)

suppliers_bp = Blueprint("suppliers", __name__)


@suppliers_bp.route("/", methods=["GET"])
def list_view():
    """
    Pagina elenco fornitori.

    Mostra:
    - dati fornitore
    - numero fatture
    - totale importi fatturati
    """
    search_term = request.args.get("q") or None
    suppliers_stats = list_suppliers_with_stats(search_term=search_term)
    return render_template(
        "suppliers/list.html",
        suppliers_stats=suppliers_stats,
        search_term=search_term or "",
    )


@suppliers_bp.route("/<int:supplier_id>", methods=["GET"])
def detail_view(supplier_id: int):
    """
    Pagina dettaglio fornitore.

    Mostra:
    - anagrafica
    - elenco fatture collegate
    """
    raw_legal_entity_id = request.args.get("legal_entity_id")
    if not raw_legal_entity_id:
        selected_legal_entity_id = None
    else:
        try:
            selected_legal_entity_id = int(raw_legal_entity_id)
        except ValueError:
            selected_legal_entity_id = None

    detail = get_supplier_detail(
        supplier_id=supplier_id,
        legal_entity_id=selected_legal_entity_id,
    )
    if detail is None:
        flash("Fornitore non trovato.", "warning")
        return redirect(url_for("suppliers.list_view"))

    detail["legal_entities"] = detail.get(
        "available_legal_entities", detail.get("legal_entities", [])
    )
    detail["selected_legal_entity_id"] = selected_legal_entity_id

    return render_template(
        "suppliers/detail.html",
        **detail,
    )


@suppliers_bp.route("/<int:supplier_id>/edit", methods=["POST"])
def edit_view(supplier_id: int):
    data = request.form
    supplier = update_supplier(
        supplier_id=supplier_id,
        name=data.get("name"),
        vat_number=data.get("vat_number"),
        fiscal_code=data.get("fiscal_code"),
        sdi_code=data.get("sdi_code"),
        pec_email=data.get("pec_email"),
        email=data.get("email"),
        iban=data.get("iban"),
        phone=data.get("phone"),
        address=data.get("address"),
        postal_code=data.get("postal_code"),
        city=data.get("city"),
        province=data.get("province"),
        country=data.get("country"),
        typical_due_rule=data.get("typical_due_rule"),
        typical_due_days=data.get("typical_due_days"),
    )
    if supplier is None:
        flash("Fornitore non trovato.", "warning")
    else:
        flash("Fornitore aggiornato.", "success")
    return redirect(url_for("suppliers.detail_view", supplier_id=supplier_id))
