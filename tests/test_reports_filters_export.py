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
        assert filter_report_category(query, [7, 8]).one() == (2, 100)


def test_csv_route_preserves_all_filters_and_escapes_names(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(routes.reports_bp)
    app.add_url_rule("/documents", endpoint="documents.list_view", view_func=lambda: "")
    monkeypatch.setattr(routes, "list_reporting_years", lambda: [2026, 2025])
    monkeypatch.setattr(routes, "list_document_types", lambda year: ["invoice"])
    monkeypatch.setattr(routes, "list_reporting_legal_entities", lambda: [{"id": 2, "name": "A"}])
    monkeypatch.setattr(routes, "list_all_categories", lambda: [SimpleNamespace(id=7, name="Servizi"), SimpleNamespace(id=8, name="Merci")])
    calls = []
    periods = []

    def monthly(year, kind, include_top_suppliers=True, legal_entity_id=None, category_id=None, date_from=None, date_to=None):
        calls.append((year, kind, legal_entity_id, category_id))
        periods.append((date_from, date_to))
        return MonthlyReport(year, [-20.0] + [0.0] * 11, [1] + [0] * 11, -20.0, 1, [None] * 12)

    def aggregate(result):
        def get(year, kind, legal_entity_id=None, category_id=None, date_from=None, date_to=None):
            calls.append((year, kind, legal_entity_id, category_id))
            return result
        return get

    monkeypatch.setattr(routes, "get_monthly_totals", monthly)
    monkeypatch.setattr(routes, "get_status_counts", aggregate({"verified": 1}))
    monkeypatch.setattr(routes, "get_top_suppliers", aggregate([
        {"supplier_id": 1, "name": '=SUM(1;2)\nCaffè', "total": -20.0, "documents": 1}
    ]))
    monkeypatch.setattr(routes, "get_category_breakdown", aggregate(CategoryBreakdown(-20.0, [
        {"category_id": 7, "name": "Servizi", "total": -20.0}
    ])))
    response = app.test_client().get("/reports/?year=2026&type=invoice&legal_entity_id=2&category_id=7&format=csv")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig")), delimiter=";"))
    assert ["Periodo", "01/01/2026 - 31/12/2026"] in rows
    assert ["Intestazione", "A"] in rows
    assert ["Categorie selezionate", "Servizi"] in rows
    assert ["Verificati", "1"] in rows
    assert ["'=SUM(1;2)\nCaffè", "1", "-20,00", "-20,00"] in rows
    assert ["Gennaio 2026", "1", "-20,00", "-20,00", "", ""] in rows
    assert ["Dicembre 2026", "0", "0,00", "0,00", "", ""] in rows
    assert len(calls) == 5
    assert all(call[1:] == ("invoice", 2, [7]) for call in calls)
    assert calls[-1][0] == 2025

    calls.clear()
    response = app.test_client().get("/reports/?category_id=999&format=csv")
    assert response.status_code == 200
    assert all(call[3] is None for call in calls)

    from datetime import date
    calls.clear()
    query = "/reports/?category_id=7&category_id=8&category_id=7&date_from=2025-12-31&date_to=2026-01-01"
    response = app.test_client().get(query + "&format=csv")
    assert response.status_code == 200
    assert len(calls) == 4  # Nessun confronto con un intero anno.
    assert all(call[3] == [7, 8] for call in calls)
    assert periods[-1] == (date(2025, 12, 31), date(2026, 1, 1))

    from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
    from pathlib import Path
    from urllib.parse import urlsplit, parse_qs
    app.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": "{% block content %}{% endblock %}"}),
        FileSystemLoader(str(Path(__file__).resolve().parents[1] / "app/templates")),
    ])
    app.jinja_env.filters["format_int"] = str
    app.jinja_env.filters["format_amount"] = str
    response = app.test_client().get(query)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'value="7" checked' in html and 'value="8" checked' in html
    assert 'value="2025-12-31"' in html
    assert "31/12/2025" in html
    import re
    from html import unescape
    link = unescape(re.search(r'href="(/documents[^"]+)"', html).group(1))
    filters = parse_qs(urlsplit(link).query)
    assert filters["category_ids"] == ["7,8"]
    assert filters["date_from"] == ["2025-12-31"]
    assert "year" not in filters



def test_report_dates_validation():
    from werkzeug.exceptions import BadRequest
    app = Flask(__name__)
    for query in ["date_from=2026-01-01", "date_to=2026-01-01",
                  "date_from=bad&date_to=2026-01-01",
                  "date_from=2026-02-30&date_to=2026-03-01",
                  "date_from=2026-03-01&date_to=2026-02-01"]:
        with app.test_request_context("/?" + query):
            try:
                routes._parse_report_dates()
            except BadRequest:
                pass
            else:
                raise AssertionError(query)
    with app.test_request_context("/?date_from=2024-02-29&date_to=2024-02-29"):
        start, end = routes._parse_report_dates()
        assert start == end


def test_aggregations_across_years_and_inclusive_dates():
    from datetime import date
    from unittest.mock import patch
    from app.services import reporting_service as service
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        raw = connection.connection.driver_connection
        raw.create_function("year", 1, lambda value: int(value[:4]))
        raw.create_function("month", 1, lambda value: int(value[5:7]))
        connection.execute(text("CREATE TABLE documents (id INTEGER, document_date DATE, document_type TEXT, legal_entity_id INTEGER, supplier_id INTEGER, doc_status TEXT, total_gross_amount NUMERIC)"))
        connection.execute(text("CREATE TABLE invoice_lines (id INTEGER, document_id INTEGER, category_id INTEGER, total_line_amount NUMERIC)"))
        connection.execute(text("CREATE TABLE suppliers (id INTEGER, name TEXT)"))
        connection.execute(text("CREATE TABLE categories (id INTEGER, name TEXT)"))
        connection.execute(text("INSERT INTO suppliers VALUES (1,'Supplier')"))
        connection.execute(text("INSERT INTO categories VALUES (7,'A'), (8,'B')"))
        connection.execute(text("INSERT INTO documents VALUES (1,'2025-12-31','invoice',2,1,'verified',120), (2,'2026-01-01','invoice',2,1,'verified',-20), (3,'2026-01-02','invoice',2,1,'verified',50), (4,'2025-12-30','invoice',2,1,'verified',70), (5,'2026-01-01','invoice',3,1,'verified',80)"))
        connection.execute(text("INSERT INTO invoice_lines VALUES (1,1,7,60), (2,1,8,60), (3,2,8,-20), (4,3,7,50), (5,4,7,70), (6,5,7,80)"))
    with Session(engine) as session, patch.object(service, "UnitOfWork") as uow:
        uow.return_value.__enter__.return_value.session = session
        scope = dict(legal_entity_id=2, category_id=[7,8],
                     date_from=date(2025,12,31), date_to=date(2026,1,1))
        monthly = service.get_monthly_totals(2026, "invoice", **scope)
        assert monthly.periods == ["2025-12", "2026-01"]
        assert monthly.values == [120.0, -20.0]
        assert monthly.counts == [1, 1]
        assert monthly.total == 100.0
        assert monthly.top_suppliers[1]["total"] == -20.0
        assert service.get_status_counts(2026, "invoice", **scope)["verified"] == 2
        suppliers = service.get_top_suppliers(2026, "invoice", **scope)
        assert suppliers[0]["total"] == 100.0
        assert suppliers[0]["documents"] == 2
        categories = service.get_category_breakdown(2026, "invoice", **scope)
        assert categories.total == 100.0
        with Flask(__name__).app_context():
            chart = routes._build_monthly_chart(monthly)
            assert chart["bars"][0]["label"] == "Dic 2025"
            assert len(chart["bars"]) == 2
        response = routes._export_csv(2026, "invoice", 2, [7,8], monthly,
                                      {}, suppliers, categories, None,
                                      scope["date_from"], scope["date_to"])
        rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig")), delimiter=";"))
        assert ["Dicembre 2025", "1", "120,00", "120,00", "Supplier", "120,00"] in rows
        assert ["Gennaio 2026", "1", "-20,00", "-20,00", "Supplier", "-20,00"] in rows
        assert ["Periodo", "31/12/2025 - 01/01/2026"] in rows
        annual = service.get_monthly_totals(2026, "invoice", legal_entity_id=2)
        assert annual.total == 30.0
        assert len(annual.values) == 12
        scope["category_id"] = [999]
        assert service.get_monthly_totals(2026, "invoice", **scope).total_documents == 0


def test_document_category_selection_parsing():
    from app.services.dto.document_filters import DocumentSearchFilters
    filters = DocumentSearchFilters.from_query_args({"category_ids": "7,8,7,no", "date_from": "2025-12-31", "date_to": "2026-01-01"})
    assert filters.category_ids == (7, 8)
    assert filters.accounting_year is None
    assert filters.date_from.year == 2025
