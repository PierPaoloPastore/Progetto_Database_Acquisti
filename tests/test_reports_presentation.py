from flask import Flask

from app.web.routes_reports import _build_category_donut, _build_report_insights, _build_monthly_chart
from app.services.reporting_service import MonthlyReport


def _app():
    app = Flask(__name__)
    app.config["FORMAT_THOUSANDS_SEPARATOR"] = "0"
    return app


def test_category_donut_groups_extra_categories():
    rows = [
        {"category_id": idx, "name": f"Categoria {idx}", "total": total, "url": f"/c/{idx}"}
        for idx, total in enumerate([60, 20, 10, 5, 3, 1, 1], start=1)
    ]
    with _app().app_context():
        donut = _build_category_donut(rows, max_slices=6)

    assert donut["has_data"] is True
    assert len(donut["segments"]) == 6
    assert donut["segments"][-1]["name"] == "Altre categorie"
    assert donut["segments"][-1]["is_other"] is True
    assert donut["segments"][-1]["children_count"] == 2
    assert round(sum(segment["percent"] for segment in donut["segments"]), 1) == 100.0


def test_category_donut_handles_empty_and_zero_values():
    rows = [
        {"category_id": 1, "name": "Zero", "total": 0, "url": "/c/1"},
        {"category_id": 2, "name": "Negativa", "total": -20, "url": "/c/2"},
        {"category_id": 3, "name": "Null", "total": None, "url": "/c/3"},
    ]
    with _app().app_context():
        donut = _build_category_donut(rows)

    assert donut["has_data"] is False
    assert donut["segments"] == []
    assert donut["total"] == 0


def test_report_insights_use_only_available_data():
    category_donut = {
        "segments": [
            {"name": "Ricambi", "percent": 25.2, "percent_label": "25,2%"},
            {"name": "Carburante", "percent": 20.0, "percent_label": "20,0%"},
            {"name": "Servizi", "percent": 10.0, "percent_label": "10,0%"},
        ]
    }
    suppliers = [{"name": "Fornitore A", "percent": 14.6}]
    chart = {"has_data": True, "max_label": "Mag", "max_total": "1000.00"}

    insights = _build_report_insights(
        category_donut=category_donut,
        suppliers_rows=suppliers,
        chart=chart,
    )

    assert len(insights) == 4
    assert "Ricambi" in insights[0]["text"]
    assert "55,2%" in insights[1]["text"]
    assert "Fornitore A" in insights[2]["text"]
    assert "Mag" in insights[3]["text"]


def test_report_insights_empty_dataset():
    insights = _build_report_insights(
        category_donut={"segments": []},
        suppliers_rows=[],
        chart={"has_data": False},
    )

    assert insights == []


def test_monthly_chart_uses_one_scale_for_positive_and_negative_amounts():
    report = MonthlyReport(2026, [100, -50, 0], [1, 1, 0], 50, 2, [None] * 3,
                           ["2026-01", "2026-02", "2026-03"])
    with _app().app_context():
        chart = _build_monthly_chart(report)
    positive, negative, zero = chart["bars"]
    assert positive["label"] == "Gen"
    assert positive["height"] == 2 * negative["height"]
    assert positive["y"] + positive["height"] == chart["base_y"]
    assert negative["y"] == chart["base_y"]
    assert zero["height"] == 0
    assert chart["ticks"][0]["y"] <= positive["y"]
    assert chart["ticks"][-1]["y"] >= negative["y"] + negative["height"]
    assert chart["left_padding"] > 0


def test_monthly_chart_handles_zero_and_negative_only_data():
    for values in ([0, 0], [-100, -50]):
        report = MonthlyReport(2026, values, [1, 1], sum(values), 2, [None, None],
                               ["2026-01", "2026-02"])
        with _app().app_context():
            chart = _build_monthly_chart(report)
        assert chart["has_data"] == any(values)
        assert all(bar["height"] >= 0 for bar in chart["bars"])
        assert chart["base_y"] == chart["ticks"][0]["y"]


def test_monthly_chart_keeps_cent_values_distinguishable():
    report = MonthlyReport(2026, [0.2, 0.1], [1, 1], 0.3, 2, [None, None],
                           ["2026-01", "2026-02"])
    with _app().app_context():
        chart = _build_monthly_chart(report)
    assert len({tick["label"] for tick in chart["ticks"]}) == 5
