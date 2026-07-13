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
    list_reporting_legal_entities,
    list_reporting_years,
)
from app.services.formatting_service import format_amount


reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

_DONUT_COLORS = [
    "#1f6f43",
    "#0d6efd",
    "#7c3aed",
    "#b7791f",
    "#0f766e",
    "#b42318",
]


@reports_bp.get("/")
def index():
    years = list_reporting_years()
    default_year = years[0] if years else date.today().year
    year = request.args.get("year", type=int) or default_year
    legal_entity_id = request.args.get("legal_entity_id", type=int)
    legal_entities = list_reporting_legal_entities()
    valid_legal_entity_ids = {row["id"] for row in legal_entities}
    if legal_entity_id not in valid_legal_entity_ids:
        legal_entity_id = None
    doc_type_filter = request.args.get("type", "all")
    document_types = list_document_types(year)
    if doc_type_filter != "all" and doc_type_filter not in document_types:
        doc_type_filter = "all"
    type_options = _build_type_options(document_types)

    monthly_report = get_monthly_totals(
        year, doc_type_filter, legal_entity_id=legal_entity_id
    )
    status_counts = get_status_counts(year, doc_type_filter, legal_entity_id)
    suppliers = get_top_suppliers(
        year, doc_type_filter, legal_entity_id=legal_entity_id
    )
    category_breakdown = get_category_breakdown(
        year, doc_type_filter, legal_entity_id=legal_entity_id
    )

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
            legal_entity_id=legal_entity_id,
        )
        previous_year_total = previous_report.total
        if previous_year_total:
            delta_amount = total_net_value - previous_year_total
            delta_percent = (delta_amount / previous_year_total) * 100

    list_filters = {"year": year}
    if legal_entity_id is not None:
        list_filters["legal_entity_id"] = legal_entity_id
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
    for row in suppliers:
        percent = (row["total"] / total_net_value * 100) if total_net_value else 0
        avg_value = row["total"] / row["documents"] if row["documents"] else 0
        suppliers_rows.append(
            {
                **row,
                "percent": percent,
                "share_percent": min(max(abs(percent), 0), 100),
                "avg": avg_value,
                "url": _list_url(supplier_id=row["supplier_id"]),
                "rank": len(suppliers_rows) + 1,
            }
        )

    category_donut = _build_category_donut(category_rows)
    report_insights = _build_report_insights(
        category_donut=category_donut,
        suppliers_rows=suppliers_rows,
        chart=chart,
    )

    return render_template(
        "reports/index.html",
        year=year,
        years=years,
        legal_entities=legal_entities,
        legal_entity_id=legal_entity_id,
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
        category_donut=category_donut,
        report_insights=report_insights,
        categories_empty=len(category_rows) == 0,
    )


def _build_monthly_chart(report) -> dict:
    labels = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
    values = report.values
    counts = report.counts
    top_suppliers = report.top_suppliers or [None] * 12
    max_value = max((abs(v) for v in values), default=0) or 1
    has_negative = any(value < 0 for value in values)

    bar_width = 28
    gap = 10
    top_padding = 10
    chart_height = 150
    chart_width = gap + (bar_width + gap) * len(labels)
    positive_height = int(chart_height * 0.68) if has_negative else chart_height
    negative_height = chart_height - positive_height if has_negative else 0
    base_y = top_padding + positive_height

    bars = []
    max_total = max(values) if values else 0
    min_total = min(values) if values else 0
    for idx, label in enumerate(labels):
        value = values[idx] if idx < len(values) else 0
        available_height = negative_height if value < 0 else positive_height
        height = int((abs(value) / max_value) * available_height)
        x = gap + idx * (bar_width + gap)
        y = base_y if value < 0 else base_y - height
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
                "raw_value": value,
                "x": x,
                "y": y,
                "width": bar_width,
                "height": max(height, 1) if value else 0,
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
        "has_data": any(value != 0 for value in values),
        "max_value": _format_amount(max_value),
        "max_label": labels[max_idx],
        "max_total": _format_amount(max_total),
        "min_label": labels[min_idx],
        "min_total": _format_amount(min_total),
        "avg_label": _format_amount(avg_value),
    }


def _format_amount(value: float) -> str:
    return format_amount(value)


def _build_category_donut(category_rows: list[dict], max_slices: int = 6) -> dict:
    positive_rows = [
        {
            **row,
            "total": float(row.get("total") or 0),
        }
        for row in category_rows
        if float(row.get("total") or 0) > 0
    ]
    positive_total = sum(row["total"] for row in positive_rows)
    if not positive_rows or positive_total <= 0:
        return {
            "has_data": False,
            "segments": [],
            "gradient": "",
            "total": 0,
            "total_label": _format_amount(0),
            "category_count": 0,
        }

    top_limit = max_slices
    if len(positive_rows) > max_slices:
        top_limit = max(1, max_slices - 1)

    visible_rows = positive_rows[:top_limit]
    extra_rows = positive_rows[top_limit:]
    if extra_rows:
        visible_rows.append(
            {
                "name": "Altre categorie",
                "total": sum(row["total"] for row in extra_rows),
                "url": None,
                "category_id": None,
                "children_count": len(extra_rows),
            }
        )

    segments = []
    cursor = 0.0
    gradient_parts = []
    for idx, row in enumerate(visible_rows):
        value = float(row["total"])
        percent = (value / positive_total * 100) if positive_total else 0
        start = cursor
        end = 100.0 if idx == len(visible_rows) - 1 else cursor + percent
        color = _DONUT_COLORS[idx % len(_DONUT_COLORS)]
        cursor = end
        gradient_parts.append(f"{color} {start:.4f}% {end:.4f}%")
        segments.append(
            {
                **row,
                "color": color,
                "percent": percent,
                "percent_label": _format_percent(percent),
                "total_label": _format_amount(value),
                "is_other": row.get("category_id") is None,
            }
        )

    return {
        "has_data": True,
        "segments": segments,
        "gradient": ", ".join(gradient_parts),
        "total": positive_total,
        "total_label": _format_amount(positive_total),
        "category_count": len(positive_rows),
    }


def _build_report_insights(
    *,
    category_donut: dict,
    suppliers_rows: list[dict],
    chart: dict,
) -> list[dict]:
    insights = []

    segments = category_donut.get("segments") or []
    if segments:
        top_category = segments[0]
        insights.append(
            {
                "icon": "bi-pie-chart",
                "text": (
                    f"{top_category['name']} rappresenta "
                    f"il {top_category['percent_label']} della spesa categorizzata."
                ),
            }
        )
        first_three = segments[:3]
        if len(first_three) >= 2:
            top_three_percent = sum(float(row.get("percent") or 0) for row in first_three)
            insights.append(
                {
                    "icon": "bi-layers",
                    "text": (
                        f"Le prime {len(first_three)} categorie concentrano "
                        f"il {_format_percent(top_three_percent)} del totale categorizzato."
                    ),
                }
            )

    if suppliers_rows:
        top_supplier = suppliers_rows[0]
        insights.append(
            {
                "icon": "bi-building",
                "text": (
                    f"{top_supplier['name']} pesa per il "
                    f"{_format_percent(top_supplier.get('percent') or 0)} della spesa filtrata."
                ),
            }
        )

    if chart.get("has_data"):
        insights.append(
            {
                "icon": "bi-calendar3",
                "text": (
                    f"{chart['max_label']} e' il mese con la spesa piu' alta "
                    f"(EUR {chart['max_total']})."
                ),
            }
        )

    return insights


def _format_percent(value: float) -> str:
    return f"{float(value or 0):.1f}%".replace(".", ",")


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
