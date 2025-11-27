"""
Context manager per gestire le transazioni del database.

Utilizza la sessione SQLAlchemy applicativa e delega commit/rollback
alla chiusura del contesto.
"""

from app.extensions import db


class UnitOfWork:
    """Semplice contesto transazionale basato su ``db.session``."""

    def __enter__(self):
        self.session = db.session
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        return False
