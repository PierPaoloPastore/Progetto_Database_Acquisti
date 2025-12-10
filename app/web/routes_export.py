"""
Route per l'export dei dati (CSV).

In questa versione aggiornata:
- Usa search_documents (invece di search_invoices)
- Rimuove il campo 'payment_status' che non esiste più in Document
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

# FIX: Importiamo search_documents dal nuovo servizio
from app.services import search_documents
from app.services.dto import DocumentSearchFilters


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
    """
    date_from = _parse_date(request.args.get("date_from", ""))
    date_to = _parse_date(request.args.get("date_to", ""))

    # FIX: Chiamata a search_documents specificando il tipo 'invoice'
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

    # Intestazione CSV
    # Nota: payment_status rimosso perché non esiste più su Document
    writer.writerow(
        [
            "invoice_id",
            "document_number",
            "document_date",
            "supplier_name",
            "total_gross_amount",
            "doc_status", 
        ]
    )

    for inv in invoices:
        supplier_name = inv.supplier.name if inv.supplier else ""
        writer.writerow(
            [
                inv.id,
                inv.document_number or "",
                inv.document_date.isoformat() if inv.document_date else "",
                supplier_name,
                str(inv.total_gross_amount or ""),
                inv.doc_status or "",
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