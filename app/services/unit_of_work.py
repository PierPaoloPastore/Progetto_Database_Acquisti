"""
Unit of Work Pattern.
Gestisce la transazione del database atomica e l'accesso ai repository.
"""
from typing import Optional
from app.extensions import db
# Importa i repository specifici
from app.repositories.category_repo import CategoryRepository

class UnitOfWork:
    def __init__(self):
        self.session = db.session
        self._categories: Optional[CategoryRepository] = None

    def __enter__(self):
        """Inizio del blocco 'with'."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Fine del blocco 'with'. 
        Gestisce il rollback in caso di eccezione.
        """
        if exc_type:
            self.rollback()
            # Lasciamo risalire l'errore
            return False
        
        # FIX: NON chiudere la sessione qui!
        # Flask-SQLAlchemy gestisce la chiusura della sessione automaticamente
        # alla fine della richiesta web ("teardown").
        # Se chiudiamo qui, non possiamo leggere i dati dell'oggetto nel Controller.
        # self.session.close()  <-- RIMOSSO

    @property
    def categories(self) -> CategoryRepository:
        """Accesso al repository Categories inizializzato con la sessione corrente."""
        if self._categories is None:
            self._categories = CategoryRepository(self.session)
        return self._categories

    def commit(self):
        """Esegue il commit della transazione."""
        try:
            self.session.commit()
        except Exception:
            self.rollback()
            raise

    def rollback(self):
        """Esegue il rollback della transazione."""
        self.session.rollback()