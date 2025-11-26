from __future__ import annotations

"""
Repository per il modello LegalEntity.

Espone funzioni basilari di lettura per recuperare le società intestatarie
(attive e non) e accedere a un singolo record per ID.
"""

from typing import Iterable, Optional

from app.models import LegalEntity


def list_legal_entities(include_inactive: bool = True) -> Iterable[LegalEntity]:
    """Restituisce l'elenco delle società intestatarie, opzionalmente solo attive."""
    query = LegalEntity.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.order_by(LegalEntity.name.asc()).all()


def get_legal_entity_by_id(legal_entity_id: int) -> Optional[LegalEntity]:
    """Restituisce una LegalEntity dato il suo ID."""
    return LegalEntity.query.get(legal_entity_id)
