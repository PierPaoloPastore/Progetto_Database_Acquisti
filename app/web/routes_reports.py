"""
Route web per la reportistica.
"""
from __future__ import annotations

from datetime import date
from typing import List

from flask import Blueprint, render_template, request

from app.services.reporting_service import (
    get_category_breakdown,
    get_monthly_totals,
    get_status_counts,
    get_top_suppliers,
    list_document_types,
    list_reporting_years,
)


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
    top_suppliers = get_top_suppliers(year, doc_type_filter, limit=6)
    category_rows = get_category_breakdown(year, doc_type_filter, limit=8)

    total_documents = sum(status_counts.values())
    chart = _build_monthly_chart(monthly_report.values)
    category_chart = _build_category_chart(category_rows)

    return render_template(
        "reports/index.html",
        year=year,
        years=years,
        doc_type_filter=doc_type_filter,
        type_options=type_options,
        total_documents=total_documents,
        total_net=_format_amount(monthly_report.total),
        status_counts=status_counts,
        chart=chart,
        top_suppliers=top_suppliers,
        category_chart=category_chart,
    )


def _build_monthly_chart(values: List[float]) -> dict:
    labels = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
    max_value = max((abs(v) for v in values), default=0) or 1

    bar_width = 28
    gap = 12
    top_padding = 8
    chart_height = 160
    chart_width = gap + (bar_width + gap) * len(labels)
    base_y = top_padding + chart_height

    bars = []
    for idx, label in enumerate(labels):
        value = values[idx] if idx < len(values) else 0
        height = int((abs(value) / max_value) * chart_height)
        x = gap + idx * (bar_width + gap)
        y = base_y - height
        bars.append(
            {
                "label": label,
                "value": _format_amount(value),
                "is_negative": value < 0,
                "x": x,
                "y": y,
                "width": bar_width,
                "height": height,
            }
        )

    return {
        "width": chart_width,
        "height": chart_height,
        "base_y": base_y,
        "bars": bars,
        "max_value": _format_amount(max_value),
    }


def _format_amount(value: float) -> str:
    return f"{value:.2f}"

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


def _build_category_chart(rows: List[dict]) -> dict:
    max_total = max((abs(row["total"]) for row in rows), default=0) or 1
    bar_height = 22
    gap = 12
    left_pad = 140
    right_pad = 40
    chart_width = 520
    bar_area = chart_width - left_pad - right_pad
    height = max(1, len(rows)) * (bar_height + gap) + gap

    bars = []
    for idx, row in enumerate(rows):
        total = row["total"]
        width = int((abs(total) / max_total) * bar_area)
        y = gap + idx * (bar_height + gap)
        label = row["name"]
        if len(label) > 22:
            label = f"{label[:19]}..."
        bars.append(
            {
                "label": label,
                "full_label": row["name"],
                "value": _format_amount(total),
                "is_negative": total < 0,
                "x": left_pad,
                "y": y,
                "width": width,
                "height": bar_height,
            }
        )

    return {
        "width": chart_width,
        "height": height,
        "bars": bars,
        "left_pad": left_pad,
    }
