"""
Repository per il modello InvoiceLine.

Contiene funzioni di utilità per accedere alle righe fattura.
"""

from typing import List, Optional

from app.extensions import db
from app.models import InvoiceLine


def get_invoice_line_by_id(line_id: int) -> Optional[InvoiceLine]:
    """Restituisce una riga fattura dato il suo ID, oppure None se non trovata."""
    return InvoiceLine.query.get(line_id)


def list_lines_by_invoice(invoice_id: int) -> List[InvoiceLine]:
    """Restituisce tutte le righe associate a una fattura."""
    return (
        InvoiceLine.query.filter_by(invoice_id=invoice_id)
        .order_by(InvoiceLine.line_number.asc().nullslast())
        .all()
    )


def list_lines_by_category(category_id: int) -> List[InvoiceLine]:
    """Restituisce tutte le righe associate a una determinata categoria gestionale."""
    return (
        InvoiceLine.query.filter_by(category_id=category_id)
        .order_by(InvoiceLine.invoice_id.asc(), InvoiceLine.line_number.asc())
        .all()
    )


def create_invoice_line(**kwargs) -> InvoiceLine:
    """
    Crea una nuova riga fattura e la aggiunge alla sessione.

    Non esegue il commit.
    """
    line = InvoiceLine(**kwargs)
    db.session.add(line)
    return line


def update_invoice_line(line: InvoiceLine, **kwargs) -> InvoiceLine:
    """
    Aggiorna i campi di una riga fattura esistente.

    I campi da aggiornare vengono passati come kwargs.
    """
    for key, value in kwargs.items():
        if hasattr(line, key):
            setattr(line, key, value)
    return line
