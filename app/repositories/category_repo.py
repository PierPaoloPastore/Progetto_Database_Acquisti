"""
Repository per il modello Category.

Gestisce le operazioni di lettura/creazione/aggiornamento delle categorie gestionali.
"""

from typing import List, Optional

from app.extensions import db
from app.models import Category
from typing import List, Optional, Any


def get_category_by_id(category_id: int) -> Optional[Category]:
    """Restituisce una categoria dato il suo ID, oppure None se non trovata."""
    return Category.query.get(category_id)


def get_category_by_name(name: str) -> Optional[Category]:
    """Restituisce una categoria dato il suo nome, se esiste."""
    if not name:
        return None
    return Category.query.filter_by(name=name).first()


def list_categories(include_inactive: bool = True) -> List[Category]:
    """
    Restituisce l'elenco delle categorie.

    :param include_inactive: se False, mostra solo quelle attive.
    """
    query = Category.query.order_by(Category.name.asc())
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.all()


def list_active_categories() -> List[Category]:
    """Shortcut per ottenere solo le categorie attive."""
    return list_categories(include_inactive=False)


def create_category(**kwargs) -> Category:
    """
    Crea una nuova categoria e la aggiunge alla sessione.

    Non esegue il commit.
    """
    category = Category(**kwargs)
    db.session.add(category)
    return category


def update_category(category: Category, **kwargs) -> Category:
    """
    Aggiorna i campi di una categoria esistente.

    I campi da aggiornare vengono passati come kwargs.
    """
    for key, value in kwargs.items():
        if hasattr(category, key):
            setattr(category, key, value)
    return category


