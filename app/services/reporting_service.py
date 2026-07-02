"""
Servizi per la reportistica (aggregazioni e KPI).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from sqlalchemy import func

from app.models import Category, Document, DocumentLine, LegalEntity, Supplier
from app.services.unit_of_work import UnitOfWork


@dataclass
class MonthlyReport:
    year: int
    values: List[float]
    counts: List[int]
    total: float
    total_documents: int
    top_suppliers: List[dict | None]


@dataclass
class CategoryBreakdown:
    total: float
    rows: List[dict]


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


def list_reporting_legal_entities() -> List[dict]:
    """Restituisce le intestazioni presenti nei documenti, ordinate per nome."""
    with UnitOfWork() as uow:
        rows = (
            uow.session.query(LegalEntity.id, LegalEntity.name)
            .join(Document, Document.legal_entity_id == LegalEntity.id)
            .distinct()
            .order_by(LegalEntity.name.asc())
            .all()
        )
    return [{"id": row[0], "name": row[1]} for row in rows]


def get_supplier_spending_report(
    legal_entity_id: int | None = None,
    year: int | None = None,
) -> List[dict]:
    """Aggrega numero documenti e spesa lorda per fornitore."""
    with UnitOfWork() as uow:
        query = (
            uow.session.query(
                Supplier.id,
                Supplier.name,
                Supplier.vat_number,
                Supplier.fiscal_code,
                func.count(Document.id),
                func.coalesce(func.sum(Document.total_gross_amount), 0),
            )
            .join(Document, Document.supplier_id == Supplier.id)
        )
        query = _apply_scope_filters(query, year=year, legal_entity_id=legal_entity_id)
        rows = (
            query.group_by(
                Supplier.id,
                Supplier.name,
                Supplier.vat_number,
                Supplier.fiscal_code,
            )
            .order_by(Supplier.name.asc())
            .all()
        )
    return [
        {
            "supplier_id": supplier_id,
            "name": name,
            "vat_number": vat_number,
            "fiscal_code": fiscal_code,
            "documents": int(documents or 0),
            "total": float(total or 0),
        }
        for supplier_id, name, vat_number, fiscal_code, documents, total in rows
    ]


def get_monthly_totals(
    year: int,
    doc_type_filter: str,
    include_top_suppliers: bool = True,
    legal_entity_id: int | None = None,
) -> MonthlyReport:
    if not year:
        year = date.today().year

    values = [0.0] * 12
    counts = [0] * 12
    top_suppliers: List[dict | None] = [None] * 12
    with UnitOfWork() as uow:
        query = (
            uow.session.query(
                func.month(Document.document_date),
                func.coalesce(func.sum(Document.total_gross_amount), 0),
                func.count(Document.id),
            )
            .filter(Document.document_date.isnot(None))
            .filter(func.year(Document.document_date) == year)
        )
        query = _apply_report_filters(query, doc_type_filter, legal_entity_id)
        rows = (
            query.group_by(func.month(Document.document_date))
            .order_by(func.month(Document.document_date))
            .all()
        )

    for month, total, count in rows:
        idx = int(month) - 1
        if 0 <= idx < 12:
            values[idx] = float(total or 0)
            counts[idx] = int(count or 0)

    if include_top_suppliers:
        with UnitOfWork() as uow:
            top_query = (
                uow.session.query(
                    func.month(Document.document_date),
                    Supplier.name,
                    func.coalesce(func.sum(Document.total_gross_amount), 0),
                )
                .join(Supplier, Supplier.id == Document.supplier_id)
                .filter(Document.document_date.isnot(None))
                .filter(func.year(Document.document_date) == year)
            )
            top_query = _apply_report_filters(
                top_query, doc_type_filter, legal_entity_id
            )
            top_rows = (
                top_query.group_by(func.month(Document.document_date), Supplier.id, Supplier.name)
                .order_by(func.month(Document.document_date), func.sum(Document.total_gross_amount).desc())
                .all()
            )

        for month, name, total in top_rows:
            idx = int(month) - 1
            if 0 <= idx < 12 and top_suppliers[idx] is None:
                top_suppliers[idx] = {
                    "name": name,
                    "total": float(total or 0),
                }

    total_sum = float(sum(values))
    total_documents = int(sum(counts))
    return MonthlyReport(
        year=year,
        values=values,
        counts=counts,
        total=total_sum,
        total_documents=total_documents,
        top_suppliers=top_suppliers,
    )


def get_status_counts(
    year: int,
    doc_type_filter: str,
    legal_entity_id: int | None = None,
) -> dict[str, int]:
    with UnitOfWork() as uow:
        query = (
            uow.session.query(Document.doc_status, func.count(Document.id))
            .filter(Document.document_date.isnot(None))
            .filter(func.year(Document.document_date) == year)
        )
        query = _apply_report_filters(query, doc_type_filter, legal_entity_id)
        rows = query.group_by(Document.doc_status).all()
    counts = {"pending_physical_copy": 0, "verified": 0, "archived": 0}
    for status, count in rows:
        if status in counts:
            counts[status] = int(count)
    return counts


def get_top_suppliers(
    year: int,
    doc_type_filter: str,
    limit: int | None = None,
    legal_entity_id: int | None = None,
) -> List[dict]:
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
        query = _apply_report_filters(query, doc_type_filter, legal_entity_id)
        rows_query = (
            query.group_by(Supplier.id, Supplier.name)
            .order_by(func.sum(Document.total_gross_amount).desc())
        )
        if limit is not None:
            rows_query = rows_query.limit(limit)
        rows = rows_query.all()

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


def get_category_breakdown(
    year: int,
    doc_type_filter: str,
    limit: int | None = None,
    legal_entity_id: int | None = None,
) -> CategoryBreakdown:
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
        query = _apply_report_filters(query, doc_type_filter, legal_entity_id)
        rows_query = (
            query.group_by(Category.id, Category.name)
            .order_by(func.sum(DocumentLine.total_line_amount).desc())
        )
        if limit is not None:
            rows_query = rows_query.limit(limit)
        rows = rows_query.all()

        total_query = (
            uow.session.query(func.coalesce(func.sum(DocumentLine.total_line_amount), 0))
            .join(Document, Document.id == DocumentLine.document_id)
            .filter(Document.document_date.isnot(None))
            .filter(func.year(Document.document_date) == year)
        )
        total_query = _apply_report_filters(
            total_query, doc_type_filter, legal_entity_id
        )
        total_sum = float(total_query.scalar() or 0)

    results = []
    for category_id, name, total in rows:
        results.append(
            {
                "category_id": category_id,
                "name": name,
                "total": float(total or 0),
            }
        )
    return CategoryBreakdown(total=total_sum, rows=results)


def _apply_type_filter(query, doc_type_filter: str):
    if doc_type_filter and doc_type_filter != "all":
        return query.filter(Document.document_type == doc_type_filter)
    return query


def _apply_report_filters(query, doc_type_filter: str, legal_entity_id: int | None):
    query = _apply_type_filter(query, doc_type_filter)
    return _apply_scope_filters(query, legal_entity_id=legal_entity_id)


def _apply_scope_filters(
    query,
    *,
    year: int | None = None,
    legal_entity_id: int | None = None,
):
    if year is not None:
        query = query.filter(Document.document_date.isnot(None))
        query = query.filter(func.year(Document.document_date) == year)
    if legal_entity_id is not None:
        query = query.filter(Document.legal_entity_id == legal_entity_id)
    return query
