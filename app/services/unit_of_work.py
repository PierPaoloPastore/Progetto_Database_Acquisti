from __future__ import annotations

"""
Context manager per gestire automaticamente commit e rollback delle operazioni
sul database.

Utilizzo:

    with UnitOfWork() as session:
        session.add(obj)
        ...  # altre operazioni

Al termine del blocco, se non vengono sollevate eccezioni viene eseguito un
commit; in caso contrario viene effettuato un rollback automatico.
"""

from app.extensions import db


class UnitOfWork:
    def __enter__(self):
        self.session = db.session
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
            return False
        self.session.commit()
        return False
