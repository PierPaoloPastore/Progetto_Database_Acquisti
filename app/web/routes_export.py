"""
Route per l'export dei dati (CSV).

In questa prima versione:
- pagina opzioni export (GET /export/)
- export elenco fatture in CSV (GET /export/invoices)
  con filtri base su intervallo di date.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from flask import (
    Blueprint,
    request,
    Response,
    render_template,
)

from app.services import search_invoices


export_bp = Blueprint("export", __name__)


def _parse_date(value: str) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


@export_bp.route("/", methods=["GET"])
def options_view():
    """
    Pagina opzioni export.

    Permette di scegliere un intervallo di date e scaricare il CSV.
    """
    return render_template("export/export_options.html")


@export_bp.route("/invoices", methods=["GET"])
def export_invoices_csv():
    """
    Esporta in CSV un elenco di fatture filtrate per intervallo di date.

    Querystring accettate:
    - date_from, date_to (YYYY-MM-DD)

    CSV generato con colonne essenziali:
    - invoice_id
    - invoice_number
    - invoice_date
    - supplier_name
    - total_gross_amount
    - payment_status
    """
    date_from = _parse_date(request.args.get("date_from", ""))
    date_to = _parse_date(request.args.get("date_to", ""))

    invoices = search_invoices(
        date_from=date_from,
        date_to=date_to,
        supplier_id=None,
        payment_status=None,
        min_total=None,
        max_total=None,
        limit=None,  # nessun limite, li prendiamo tutti nel range
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    # Intestazione CSV
    writer.writerow(
        [
            "invoice_id",
            "invoice_number",
            "invoice_date",
            "supplier_name",
            "total_gross_amount",
            "payment_status",
        ]
    )

    for inv in invoices:
        supplier_name = inv.supplier.name if inv.supplier else ""
        writer.writerow(
            [
                inv.id,
                inv.invoice_number or "",
                inv.invoice_date.isoformat() if inv.invoice_date else "",
                supplier_name,
                str(inv.total_gross_amount or ""),
                inv.payment_status or "",
            ]
        )

    csv_data = output.getvalue()
    output.close()

    filename = "invoices_export.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )
