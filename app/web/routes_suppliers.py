"""
Route per la gestione dei fornitori (Supplier).

Comprende:
- elenco fornitori con statistiche base (GET /suppliers/)
- dettaglio fornitore con elenco fatture (GET /suppliers/<id>)
"""

from __future__ import annotations

import csv
import io

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from app.services import (
    create_supplier,
    list_suppliers_with_stats,
    get_supplier_detail,
    update_supplier,
)
from app.services.reporting_service import (
    get_supplier_spending_report,
    list_reporting_legal_entities,
    list_reporting_years,
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
    legal_entities = list_reporting_legal_entities()
    years = list_reporting_years()
    return render_template(
        "suppliers/list.html",
        suppliers_stats=suppliers_stats,
        search_term=search_term or "",
        legal_entities=legal_entities,
        years=years,
    )


@suppliers_bp.get("/spending-report.csv")
def spending_report_csv():
    """Esporta le spese aggregate di tutti i fornitori per intestazione/anno."""
    legal_entity_id = request.args.get("legal_entity_id", type=int)
    year = request.args.get("year", type=int)
    legal_entities = list_reporting_legal_entities()
    entity_by_id = {row["id"]: row["name"] for row in legal_entities}
    if legal_entity_id not in entity_by_id:
        legal_entity_id = None

    rows = get_supplier_spending_report(
        legal_entity_id=legal_entity_id,
        year=year,
    )
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\r\n")
    writer.writerow(
        [
            "Intestazione",
            "Anno",
            "Fornitore",
            "Partita IVA",
            "Codice fiscale",
            "Numero documenti",
            "Spesa totale",
        ]
    )
    entity_name = entity_by_id.get(legal_entity_id, "Tutte")
    for row in rows:
        writer.writerow(
            [
                entity_name,
                year or "Tutti",
                row["name"],
                row["vat_number"] or "",
                row["fiscal_code"] or "",
                row["documents"],
                f'{row["total"]:.2f}'.replace(".", ","),
            ]
        )

    filename_parts = ["spese_fornitori"]
    if legal_entity_id:
        filename_parts.append(str(legal_entity_id))
    if year:
        filename_parts.append(str(year))
    filename = "_".join(filename_parts) + ".csv"
    return Response(
        "\ufeff" + output.getvalue(),
        content_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@suppliers_bp.route("/create", methods=["POST"])
def create_view():
    data = request.form
    supplier, error = create_supplier(
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
    )
    if error:
        flash(error, "warning")
        return redirect(url_for("suppliers.list_view", open_new=1))

    flash("Fornitore creato.", "success")
    return redirect(url_for("suppliers.detail_view", supplier_id=supplier.id))


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
        is_active=data.get("is_active"),
    )
    if supplier is None:
        flash("Fornitore non trovato.", "warning")
    else:
        flash("Fornitore aggiornato.", "success")
    return redirect(url_for("suppliers.detail_view", supplier_id=supplier_id))
