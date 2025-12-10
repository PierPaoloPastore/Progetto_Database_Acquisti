"""
Route per la gestione delle categorie (Category).

Comprende:
- elenco categorie (GET /categories/)
- creazione/aggiornamento categoria (POST /categories/save)
- assegnazione bulk di categoria alle righe documento (POST /categories/bulk-assign)
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
    """
    categories = list_categories_for_ui()
    return render_template(
        "categories/list.html",
        categories=categories,
    )


@categories_bp.route("/save", methods=["POST"])
def save_view():
    """
    Crea o aggiorna una categoria.
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


# FIX: invoice_id -> document_id
@categories_bp.route("/bulk-assign/<int:document_id>", methods=["GET", "POST"])
def bulk_assign_view(document_id: int):
    """
    Schermata per l'assegnazione bulk di una categoria alle righe di un documento.
    """
    if request.method == "GET":
        categories = list_categories_for_ui()
        # Nota: la funzione repo si chiama ancora list_lines_by_invoice ma accetta document_id
        lines = list_lines_by_invoice(document_id)
        
        return render_template(
            "categories/assign_bulk.html",
            document_id=document_id, # FIX: passiamo document_id
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
        temp: List[int] = []
        for v in selected_line_ids:
            try:
                temp.append(int(v))
            except ValueError:
                continue
        line_ids = temp

    # La funzione del service accetta ancora 'invoice_id' come nome parametro formale,
    # ma semanticamente è un document_id. Lo passiamo posizionale o keyword.
    result = bulk_assign_category_to_invoice_lines(
        invoice_id=document_id, 
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

    # FIX: Redirect a documents.detail_view
    return redirect(url_for("documents.detail_view", document_id=document_id))