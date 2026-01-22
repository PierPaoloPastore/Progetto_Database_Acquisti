"""
Route web per la reportistica.
"""
from __future__ import annotations

from datetime import date, datetime


from flask import Blueprint, render_template, request, url_for

from app.services.reporting_service import (
    get_category_breakdown,
    get_monthly_totals,
    get_status_counts,
    get_top_suppliers,
    list_document_types,
    list_reporting_years,
)
from app.services.formatting_service import format_amount


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.get("/")
def index():
    years = list_reporting_years()
    default_year = years[0] if years else date.today().year
    year = request.args.get("year", type=int) or default_year
    doc_type_filter = request.args.get("type", "all")
    document_types = list_document_types(year)
    if doc_type_filter != "all" and doc_type_filter not in document_types:
        doc_type_filter = "all"
    type_options = _build_type_options(document_types)

    monthly_report = get_monthly_totals(year, doc_type_filter)
    status_counts = get_status_counts(year, doc_type_filter)
    top_suppliers = get_top_suppliers(year, doc_type_filter, limit=10)
    category_breakdown = get_category_breakdown(year, doc_type_filter, limit=10)

    total_documents = monthly_report.total_documents
    total_net_value = monthly_report.total
    average_per_document = total_net_value / total_documents if total_documents else 0
    verified_count = status_counts.get("verified", 0)
    pending_count = status_counts.get("pending_physical_copy", 0)
    verified_percent = (verified_count / total_documents * 100) if total_documents else 0

    previous_year_total = None
    delta_amount = None
    delta_percent = None
    if (year - 1) in years:
        previous_report = get_monthly_totals(
            year - 1,
            doc_type_filter,
            include_top_suppliers=False,
        )
        previous_year_total = previous_report.total
        if previous_year_total:
            delta_amount = total_net_value - previous_year_total
            delta_percent = (delta_amount / previous_year_total) * 100

    list_filters = {"year": year}
    if doc_type_filter != "all":
        list_filters["document_type"] = doc_type_filter

    def _list_url(**kwargs: dict) -> str:
        params = dict(list_filters)
        params.update(kwargs)
        return url_for("documents.list_view", **params)

    links = {
        "total_net": _list_url(),
        "documents": _list_url(),
        "pending": _list_url(doc_status="pending_physical_copy"),
        "verified": _list_url(doc_status="verified"),
        "uncategorized": _list_url(category_unassigned=1),
    }

    chart = _build_monthly_chart(monthly_report)
    category_rows = []
    category_total_base = category_breakdown.total or total_net_value
    if category_total_base < 0:
        category_total_base = abs(category_total_base)
    for row in category_breakdown.rows:
        percent = (row["total"] / category_total_base * 100) if category_total_base else 0
        category_rows.append(
            {
                **row,
                "percent": percent,
                "url": _list_url(category_id=row["category_id"]),
            }
        )

    suppliers_rows = []
    for row in top_suppliers:
        percent = (row["total"] / total_net_value * 100) if total_net_value else 0
        avg_value = row["total"] / row["documents"] if row["documents"] else 0
        suppliers_rows.append(
            {
                **row,
                "percent": percent,
                "avg": avg_value,
                "url": _list_url(supplier_id=row["supplier_id"]),
            }
        )

    return render_template(
        "reports/index.html",
        year=year,
        years=years,
        doc_type_filter=doc_type_filter,
        type_options=type_options,
        total_documents=total_documents,
        total_net=_format_amount(total_net_value),
        total_net_value=total_net_value,
        average_per_document=_format_amount(average_per_document),
        previous_year_total=_format_amount(previous_year_total) if previous_year_total is not None else None,
        delta_amount=_format_amount(delta_amount) if delta_amount is not None else None,
        delta_percent=delta_percent,
        pending_count=pending_count,
        verified_count=verified_count,
        verified_percent=verified_percent,
        status_counts=status_counts,
        last_updated=datetime.now().strftime("%d/%m/%Y %H:%M"),
        links=links,
        chart=chart,
        top_suppliers=suppliers_rows,
        category_rows=category_rows,
        categories_empty=len(category_rows) == 0,
    )


def _build_monthly_chart(report) -> dict:
    labels = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
    values = report.values
    counts = report.counts
    top_suppliers = report.top_suppliers or [None] * 12
    max_value = max((abs(v) for v in values), default=0) or 1

    bar_width = 24
    gap = 8
    top_padding = 4
    chart_height = 110
    chart_width = gap + (bar_width + gap) * len(labels)
    base_y = top_padding + chart_height

    bars = []
    max_total = max(values) if values else 0
    min_total = min(values) if values else 0
    for idx, label in enumerate(labels):
        value = values[idx] if idx < len(values) else 0
        height = int((abs(value) / max_value) * chart_height)
        x = gap + idx * (bar_width + gap)
        y = base_y - height
        top_supplier = top_suppliers[idx] if idx < len(top_suppliers) else None
        top_supplier_label = "n/d"
        if top_supplier:
            top_supplier_label = f"{top_supplier['name']} (€ { _format_amount(top_supplier['total']) })"
        formatted_value = _format_amount(value)
        tooltip = (
            f"{label} | € {formatted_value}\n"
            f"Documenti: {counts[idx] if idx < len(counts) else 0}\n"
            f"Top fornitore: {top_supplier_label}"
        )
        bars.append(
            {
                "label": label,
                "value": formatted_value,
                "documents": counts[idx] if idx < len(counts) else 0,
                "top_supplier": top_supplier_label,
                "tooltip": tooltip,
                "is_max": value == max_total,
                "is_min": value == min_total,
                "is_negative": value < 0,
                "x": x,
                "y": y,
                "width": bar_width,
                "height": height,
            }
        )

    avg_value = report.total / 12 if report.total else 0
    max_idx = values.index(max_total) if values else 0
    min_idx = values.index(min_total) if values else 0
    return {
        "width": chart_width,
        "height": chart_height,
        "base_y": base_y,
        "bars": bars,
        "max_value": _format_amount(max_value),
        "max_label": labels[max_idx],
        "max_total": _format_amount(max_total),
        "min_label": labels[min_idx],
        "min_total": _format_amount(min_total),
        "avg_label": _format_amount(avg_value),
    }


def _format_amount(value: float) -> str:
    return format_amount(value)

def _build_type_options(document_types: list[str]) -> list[dict]:
    labels = {
        "invoice": "Fatture",
        "credit_note": "Note di credito",
        "f24": "F24",
        "insurance": "Assicurazioni",
        "mav": "MAV",
        "cbill": "CBILL",
        "receipt": "Scontrini",
        "rent": "Affitti",
        "tax": "Tributi",
        "other": "Altro",
    }
    options = [{"value": "all", "label": "Tutti i documenti"}]
    for doc_type in document_types:
        label = labels.get(doc_type, doc_type.replace("_", " ").title())
        options.append({"value": doc_type, "label": label})
    return options
