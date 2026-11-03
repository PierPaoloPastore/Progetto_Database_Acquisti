"""Filtri condivisi per le query di reportistica."""
from datetime import date

from sqlalchemy import func

from app.models import Document, DocumentLine, LegalEntity


def filter_report_category(query, category_id: int | list[int] | tuple[int, ...] | None):
    if category_id:
        category_ids = [category_id] if isinstance(category_id, int) else category_id
        query = query.filter(
            Document.invoice_lines.any(DocumentLine.category_id.in_(category_ids))
        )
    return query


def filter_report_period(query, year: int, date_from: date | None = None,
                         date_to: date | None = None):
    start = date_from or date(year, 1, 1)
    end = date_to or date(year, 12, 31)
    return query.filter(Document.document_date >= start, Document.document_date <= end)


def list_category_entity_totals(session, year: int, doc_type_filter: str,
                                category_id=None, date_from: date | None = None,
                                date_to: date | None = None):
    """Somma le righe per categoria e intestazione, senza duplicare i documenti."""
    query = (
        session.query(
            DocumentLine.category_id, LegalEntity.id, LegalEntity.name,
            func.coalesce(func.sum(DocumentLine.total_line_amount), 0),
        )
        .join(Document, Document.id == DocumentLine.document_id)
        .outerjoin(LegalEntity, LegalEntity.id == Document.legal_entity_id)
        .filter(DocumentLine.category_id.isnot(None))
    )
    query = filter_report_period(query, year, date_from, date_to)
    query = filter_report_category(query, category_id)
    if doc_type_filter and doc_type_filter != "all":
        query = query.filter(Document.document_type == doc_type_filter)
    return (
        query.group_by(DocumentLine.category_id, LegalEntity.id, LegalEntity.name)
        .order_by(DocumentLine.category_id, func.sum(DocumentLine.total_line_amount).desc(),
                  LegalEntity.name, LegalEntity.id)
        .all()
    )
