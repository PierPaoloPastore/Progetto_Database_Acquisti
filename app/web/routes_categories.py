"""
Route per la gestione delle categorie (Category).

Comprende:
- elenco categorie (GET /categories/)
- creazione/aggiornamento categoria (POST /categories/save)
- assegnazione bulk di categoria alle righe fattura (POST /categories/bulk-assign)
"""

from __future__ import annotations

from typing import List, Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)

from app.services import (
    list_categories_for_ui,
    create_or_update_category,
    bulk_assign_category_to_invoice_lines,
)
from app.repositories import list_lines_by_invoice

categories_bp = Blueprint("categories", __name__)


@categories_bp.route("/", methods=["GET"])
def list_view():
    """
    Pagina elenco categorie.

    Include:
    - tabella categorie
    - form base per creare/modificare una categoria
    """
    categories = list_categories_for_ui()
    return render_template(
        "categories/list.html",
        categories=categories,
    )


@categories_bp.route("/save", methods=["POST"])
def save_view():
    """
    Crea o aggiorna una categoria in base ai campi del form:

    - category_id (opzionale)
    - name
    - description
    """
    category_id_str = request.form.get("category_id") or None
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None

    if not name:
        flash("Il nome della categoria è obbligatorio.", "warning")
        return redirect(url_for("categories.list_view"))

    category_id: Optional[int] = None
    if category_id_str:
        try:
            category_id = int(category_id_str)
        except ValueError:
            category_id = None

    category = create_or_update_category(
        name=name,
        description=description,
        category_id=category_id,
    )

    flash(f"Categoria '{category.name}' salvata con successo.", "success")
    return redirect(url_for("categories.list_view"))


@categories_bp.route("/bulk-assign/<int:invoice_id>", methods=["GET", "POST"])
def bulk_assign_view(invoice_id: int):
    """
    Schermata per l'assegnazione bulk di una categoria alle righe di una fattura.

    GET:
        mostra elenco righe + select categoria + possibilità di selezionare righe
    POST:
        applica la categoria scelta alle righe selezionate (o tutte)
    """
    if request.method == "GET":
        categories = list_categories_for_ui()
        lines = list_lines_by_invoice(invoice_id)
        return render_template(
            "categories/assign_bulk.html",
            invoice_id=invoice_id,
            categories=categories,
            lines=lines,
        )

    # POST
    category_id_str = request.form.get("category_id") or None
    apply_to_all = request.form.get("apply_to_all") == "1"
    selected_line_ids = request.form.getlist("line_ids")

    category_id: Optional[int] = None
    if category_id_str:
        try:
            category_id = int(category_id_str)
        except ValueError:
            category_id = None

    line_ids: Optional[List[int]] = None
    if not apply_to_all:
        # Converto gli ID riga selezionati in interi
        temp: List[int] = []
        for v in selected_line_ids:
            try:
                temp.append(int(v))
            except ValueError:
                continue
        line_ids = temp

    result = bulk_assign_category_to_invoice_lines(
        invoice_id=invoice_id,
        category_id=category_id,
        line_ids=line_ids,
    )

    if result.get("success"):
        flash(
            f"Categoria assegnata a {result.get('updated_count', 0)} righe.",
            "success",
        )
    else:
        flash(result.get("message", "Errore durante l'assegnazione categorie."), "danger")

    return redirect(url_for("invoices.detail_view", invoice_id=invoice_id))
