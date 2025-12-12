"""
Repository specifico per Category.
Eredita le funzioni base (add, get, list) da SqlAlchemyRepository.
"""
from typing import Optional, List
from app.models import Category
from app.repositories.base import SqlAlchemyRepository

class CategoryRepository(SqlAlchemyRepository[Category]):
    def __init__(self, session):
        # Passiamo la sessione e la classe del modello al costruttore base
        super().__init__(session, Category)

    def get_by_name(self, name: str) -> Optional[Category]:
        """Cerca categoria per nome esatto."""
        if not name:
            return None
        return self.session.query(Category).filter_by(name=name).first()

    def list_active(self) -> List[Category]:
        """Ritorna solo le categorie con is_active=True, ordinate per nome."""
        return (
            self.session.query(Category)
            .filter_by(is_active=True)
            .order_by(Category.name.asc())
            .all()
        )
    
    def list_all_ordered(self) -> List[Category]:
        """Ritorna tutte le categorie ordinate per nome."""
        return self.session.query(Category).order_by(Category.name.asc()).all()