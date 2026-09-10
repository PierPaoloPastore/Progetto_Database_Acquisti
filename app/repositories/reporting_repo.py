"""Filtri condivisi per le query di reportistica."""
from datetime import date

from app.models import Document, DocumentLine


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
