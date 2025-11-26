"""
Repository per il modello Note.

Gestisce le operazioni di lettura/creazione delle note interne alle fatture.
"""

from typing import List, Optional

from app.extensions import db
from app.models import Note


def get_note_by_id(note_id: int) -> Optional[Note]:
    """Restituisce una nota dato il suo ID, oppure None se non trovata."""
    return Note.query.get(note_id)


def list_notes_by_invoice(invoice_id: int) -> List[Note]:
    """Restituisce tutte le note associate a una fattura, ordinate per data di creazione."""
    return (
        Note.query.filter_by(invoice_id=invoice_id)
        .order_by(Note.created_at.asc())
        .all()
    )


def create_note(**kwargs) -> Note:
    """
    Crea una nuova nota e la aggiunge alla sessione.

    Non esegue il commit.
    """
    note = Note(**kwargs)
    db.session.add(note)
    return note
