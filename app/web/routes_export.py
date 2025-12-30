"""
Route per l'export dei dati (CSV).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from flask import (
    Blueprint, request, Response, render_template,
)

from app.services import search_documents
from app.services.formatting_service import format_amount
# FIX: Importa DocumentSearchFilters
from app.services.dto import DocumentSearchFilters

export_bp = Blueprint("export", __name__)

def _parse_date(value: str) -> Optional[datetime.date]:
    if not value: return None
    try: return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError: return None

@export_bp.route("/", methods=["GET"])
def options_view():
    return render_template("export/export_options.html")

@export_bp.route("/invoices", methods=["GET"])
def export_invoices_csv():
    date_from = _parse_date(request.args.get("date_from", ""))
    date_to = _parse_date(request.args.get("date_to", ""))

    # FIX: Usa DocumentSearchFilters
    invoices = search_documents(
        filters=DocumentSearchFilters(
            date_from=date_from,
            date_to=date_to,
        ),
        limit=None,
        document_type='invoice'
    )

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    writer.writerow(["invoice_id", "document_number", "document_date", "supplier_name", "total_gross_amount", "doc_status"])

    for inv in invoices:
        supplier_name = inv.supplier.name if inv.supplier else ""
        writer.writerow([
            inv.id,
            inv.document_number or "",
            inv.document_date.isoformat() if inv.document_date else "",
            supplier_name,
            format_amount(inv.total_gross_amount),
            inv.doc_status or "",
        ])

    csv_data = output.getvalue()
    output.close()

    filename = "invoices_export.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
