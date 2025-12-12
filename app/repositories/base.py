"""
Generic Repository Pattern.
Fornisce le operazioni CRUD base per qualsiasi modello SQLAlchemy.
"""
from typing import Type, TypeVar, Generic, Optional, List, Any
from app.extensions import db

# Definisce un tipo generico T che deve essere un modello SQLAlchemy
T = TypeVar("T", bound=db.Model)

class SqlAlchemyRepository(Generic[T]):
    def __init__(self, session, model_cls: Type[T]):
        self.session = session
        self.model_cls = model_cls

    def add(self, entity: T) -> T:
        """Aggiunge l'entità alla sessione."""
        self.session.add(entity)
        return entity

    def get_by_id(self, id: int) -> Optional[T]:
        """Recupera per Primary Key."""
        return self.session.query(self.model_cls).get(id)

    def list_all(self) -> List[T]:
        """Ritorna tutti i record."""
        return self.session.query(self.model_cls).all()

    def delete(self, entity: T) -> None:
        """Cancella l'entità."""
        self.session.delete(entity)