"""
Route per la gestione dei fornitori (Supplier).

Comprende:
- elenco fornitori con statistiche base (GET /suppliers/)
- dettaglio fornitore con elenco fatture (GET /suppliers/<id>)
"""

from __future__ import annotations

from flask import Blueprint, render_template, redirect, url_for, flash

from app.services import (
    list_suppliers_with_stats,
    get_supplier_detail,
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
    suppliers_stats = list_suppliers_with_stats()
    return render_template(
        "suppliers/list.html",
        suppliers_stats=suppliers_stats,
    )


@suppliers_bp.route("/<int:supplier_id>", methods=["GET"])
def detail_view(supplier_id: int):
    """
    Pagina dettaglio fornitore.

    Mostra:
    - anagrafica
    - elenco fatture collegate
    """
    detail = get_supplier_detail(supplier_id)
    if detail is None:
        flash("Fornitore non trovato.", "warning")
        return redirect(url_for("suppliers.list_view"))

    return render_template(
        "suppliers/detail.html",
        **detail,
    )
