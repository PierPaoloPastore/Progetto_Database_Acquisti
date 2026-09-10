"""Filtri condivisi per le query di reportistica."""
from app.models import Document, DocumentLine


def filter_report_category(query, category_id: int | None):
    if category_id is not None:
        query = query.filter(
            Document.invoice_lines.any(DocumentLine.category_id == category_id)
        )
    return query
