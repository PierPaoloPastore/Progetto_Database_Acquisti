import csv
import io
from types import SimpleNamespace

from flask import Flask
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import Session

from app.models import Document
from app.repositories.reporting_repo import filter_report_category
from app.services.reporting_service import MonthlyReport, CategoryBreakdown
from app.web import routes_reports as routes


def test_category_filter_does_not_duplicate_multiline_documents():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE documents (id INTEGER, total_gross_amount NUMERIC)"))
        connection.execute(text("CREATE TABLE invoice_lines (id INTEGER, document_id INTEGER, category_id INTEGER)"))
        connection.execute(text("INSERT INTO documents VALUES (1, 120), (2, -20), (3, 50)"))
        connection.execute(text("INSERT INTO invoice_lines VALUES (1,1,7), (2,1,7), (3,1,8), (4,2,7), (5,3,NULL)"))
    with Session(engine) as session:
        query = session.query(func.count(Document.id), func.sum(Document.total_gross_amount))
        assert filter_report_category(query, 7).one() == (2, 100)
        assert filter_report_category(query, None).one() == (3, 150)
        assert filter_report_category(query, 99).one() == (0, None)


def test_csv_route_preserves_all_filters_and_escapes_names(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(routes.reports_bp)
    monkeypatch.setattr(routes, "list_reporting_years", lambda: [2026, 2025])
    monkeypatch.setattr(routes, "list_document_types", lambda year: ["invoice"])
    monkeypatch.setattr(routes, "list_reporting_legal_entities", lambda: [{"id": 2, "name": "A"}])
    monkeypatch.setattr(routes, "list_all_categories", lambda: [SimpleNamespace(id=7, name="Servizi")])
    calls = []

    def monthly(year, kind, include_top_suppliers=True, legal_entity_id=None, category_id=None):
        calls.append((year, kind, legal_entity_id, category_id))
        return MonthlyReport(year, [-20.0] + [0.0] * 11, [1] + [0] * 11, -20.0, 1, [None] * 12)

    def aggregate(result):
        def get(year, kind, legal_entity_id=None, category_id=None):
            calls.append((year, kind, legal_entity_id, category_id))
            return result
        return get

    monkeypatch.setattr(routes, "get_monthly_totals", monthly)
    monkeypatch.setattr(routes, "get_status_counts", aggregate({"verified": 1}))
    monkeypatch.setattr(routes, "get_top_suppliers", aggregate([
        {"name": '=SUM(1;2)\nCaffè', "total": -20.0, "documents": 1}
    ]))
    monkeypatch.setattr(routes, "get_category_breakdown", aggregate(CategoryBreakdown(-20.0, [
        {"name": "Servizi", "total": -20.0}
    ])))
    response = app.test_client().get("/reports/?year=2026&type=invoice&legal_entity_id=2&category_id=7&format=csv")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig")), delimiter=";"))
    assert ["2026", "invoice", "2", "7"] in rows
    assert ["Fornitore", "'=SUM(1;2)\nCaffè", "1", "-20,00"] in rows
    assert len([row for row in rows if row[0] == "Mese"]) == 12
    assert len(calls) == 5
    assert all(call[1:] == ("invoice", 2, 7) for call in calls)
    assert calls[-1][0] == 2025

    calls.clear()
    response = app.test_client().get("/reports/?category_id=999&format=csv")
    assert response.status_code == 200
    assert all(call[3] is None for call in calls)
