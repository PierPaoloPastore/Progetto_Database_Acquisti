"""
Servizi per la reportistica (aggregazioni e KPI).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from sqlalchemy import func

from app.models import Category, Document, DocumentLine, Supplier
from app.services.unit_of_work import UnitOfWork


@dataclass
class MonthlyReport:
    year: int
    values: List[float]
    total: float


def list_reporting_years() -> List[int]:
    with UnitOfWork() as uow:
        rows = (
            uow.session.query(func.year(Document.document_date))
            .filter(Document.document_date.isnot(None))
            .distinct()
            .order_by(func.year(Document.document_date).desc())
            .all()
        )
    return [row[0] for row in rows if row[0]]

def list_document_types(year: int | None = None) -> List[str]:
    with UnitOfWork() as uow:
        query = (
            uow.session.query(Document.document_type)
            .filter(Document.document_type.isnot(None))
        )
        if year:
            query = query.filter(Document.document_date.isnot(None))
            query = query.filter(func.year(Document.document_date) == year)
        rows = query.distinct().order_by(Document.document_type.asc()).all()
    return [row[0] for row in rows if row[0]]


def get_monthly_totals(year: int, doc_type_filter: str) -> MonthlyReport:
    if not year:
        year = date.today().year

    values = [0.0] * 12
    with UnitOfWork() as uow:
        query = (
            uow.session.query(
                func.month(Document.document_date),
                func.coalesce(func.sum(Document.total_gross_amount), 0),
            )
            .filter(Document.document_date.isnot(None))
            .filter(func.year(Document.document_date) == year)
        )
        query = _apply_type_filter(query, doc_type_filter)
        rows = (
            query.group_by(func.month(Document.document_date))
            .order_by(func.month(Document.document_date))
            .all()
        )

    for month, total in rows:
        idx = int(month) - 1
        if 0 <= idx < 12:
            values[idx] = float(total or 0)

    total_sum = float(sum(values))
    return MonthlyReport(year=year, values=values, total=total_sum)


def get_status_counts(year: int, doc_type_filter: str) -> dict[str, int]:
    with UnitOfWork() as uow:
        query = (
            uow.session.query(Document.doc_status, func.count(Document.id))
            .filter(Document.document_date.isnot(None))
            .filter(func.year(Document.document_date) == year)
        )
        query = _apply_type_filter(query, doc_type_filter)
        rows = query.group_by(Document.doc_status).all()
    counts = {"pending_physical_copy": 0, "verified": 0, "archived": 0}
    for status, count in rows:
        if status in counts:
            counts[status] = int(count)
    return counts


def get_top_suppliers(year: int, doc_type_filter: str, limit: int = 5) -> List[dict]:
    with UnitOfWork() as uow:
        query = (
            uow.session.query(
                Supplier.id,
                Supplier.name,
                func.coalesce(func.sum(Document.total_gross_amount), 0),
                func.count(Document.id),
            )
            .join(Document, Document.supplier_id == Supplier.id)
            .filter(Document.document_date.isnot(None))
            .filter(func.year(Document.document_date) == year)
        )
        query = _apply_type_filter(query, doc_type_filter)
        rows = (
            query.group_by(Supplier.id, Supplier.name)
            .order_by(func.sum(Document.total_gross_amount).desc())
            .limit(limit)
            .all()
        )

    results = []
    for supplier_id, name, total, count in rows:
        results.append(
            {
                "supplier_id": supplier_id,
                "name": name,
                "total": float(total or 0),
                "documents": int(count or 0),
            }
        )
    return results


def get_category_breakdown(year: int, doc_type_filter: str, limit: int = 8) -> List[dict]:
    with UnitOfWork() as uow:
        query = (
            uow.session.query(
                Category.id,
                Category.name,
                func.coalesce(func.sum(DocumentLine.total_line_amount), 0),
            )
            .join(DocumentLine, DocumentLine.category_id == Category.id)
            .join(Document, Document.id == DocumentLine.document_id)
            .filter(Document.document_date.isnot(None))
            .filter(func.year(Document.document_date) == year)
        )
        query = _apply_type_filter(query, doc_type_filter)
        rows = (
            query.group_by(Category.id, Category.name)
            .order_by(func.sum(DocumentLine.total_line_amount).desc())
            .limit(limit)
            .all()
        )

    results = []
    for category_id, name, total in rows:
        results.append(
            {
                "category_id": category_id,
                "name": name,
                "total": float(total or 0),
            }
        )
    return results


def _apply_type_filter(query, doc_type_filter: str):
    if doc_type_filter and doc_type_filter != "all":
        return query.filter(Document.document_type == doc_type_filter)
    return query
