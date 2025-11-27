from __future__ import annotations

"""
Context manager per gestire automaticamente commit e rollback delle operazioni
sul database.

Utilizzo:

    from app.services.unit_of_work import UnitOfWork

    with UnitOfWork() as session:
        session.add(obj)
        ...  # altre operazioni

Al termine del blocco:
- se non vengono sollevate eccezioni viene eseguito un commit;
- in caso contrario viene effettuato un rollback automatico e l'eccezione
  originale viene propagata.
"""

from app.extensions import db


class UnitOfWork:
    """Context manager per gestire una singola transazione basata su db.session."""

    def __init__(self) -> None:
        self.session = db.session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # Nessuna eccezione nel blocco with → proviamo il commit
        if exc_type is None:
            try:
                self.session.commit()
            except Exception:
                # Errore in fase di commit → rollback e rilanciamo
                self.session.rollback()
                raise
        else:
            # Eccezione avvenuta dentro il blocco with → rollback e propaghiamo
            self.session.rollback()
            return False  # False = non sopprimere l'eccezione originale

        # In assenza di eccezioni nel blocco with non c’è nulla da sopprimere,
        # ma per chiarezza torniamo comunque False.
        return False
