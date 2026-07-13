from flask import Flask

from app.web.routes_reports import _build_category_donut, _build_report_insights


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
