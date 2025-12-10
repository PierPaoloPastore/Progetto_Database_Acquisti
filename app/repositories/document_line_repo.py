"""
Repository per il modello DocumentLine.

Contiene funzioni di utilità per accedere alle righe documento.
"""
from sqlalchemy import case
from typing import List, Optional

from app.extensions import db
from app.models import DocumentLine


def get_document_line_by_id(line_id: int) -> Optional[DocumentLine]:
    """Restituisce una riga documento dato il suo ID, oppure None se non trovata."""
    return DocumentLine.query.get(line_id)


def list_lines_by_document(document_id: int) -> List[DocumentLine]:
    """Restituisce tutte le righe associate a un documento."""
    return (
        DocumentLine.query.filter_by(document_id=document_id)
        .order_by(
            case((DocumentLine.line_number.is_(None), 1), else_=0),
            DocumentLine.line_number.asc(),
        )
        .all()
    )


def list_lines_by_category(category_id: int) -> List[DocumentLine]:
    """Restituisce tutte le righe associate a una determinata categoria gestionale."""
    return (
        DocumentLine.query.filter_by(category_id=category_id)
        .order_by(DocumentLine.document_id.asc(), DocumentLine.line_number.asc())
        .all()
    )


def create_document_line(**kwargs) -> DocumentLine:
    """
    Crea una nuova riga documento e la aggiunge alla sessione.

    Non esegue il commit.
    """
    line = DocumentLine(**kwargs)
    db.session.add(line)
    return line


def update_document_line(line: DocumentLine, **kwargs) -> DocumentLine:
    """
    Aggiorna i campi di una riga documento esistente.

    I campi da aggiornare vengono passati come kwargs.
    """
    for key, value in kwargs.items():
        if hasattr(line, key):
            setattr(line, key, value)
    return line
