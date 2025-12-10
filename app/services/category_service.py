"""
Servizi per la gestione delle categorie (Category) e assegnazione alle righe documento.

Funzioni principali:
- list_categories_for_ui()
- create_or_update_category(...)
- assign_category_to_line(line_id, category_id)
- bulk_assign_category_to_invoice_lines(invoice_id, category_id, line_ids=None)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models import DocumentLine
from app.repositories import (
    list_active_categories,
    get_category_by_id,
    get_category_by_name,
    create_category,
    update_category,
    get_document_line_by_id,
    list_lines_by_document,
)


def list_categories_for_ui() -> List:
    """
    Restituisce tutte le categorie attive, ordinate per nome.

    Pensata per UI di selezione/combobox.
    """
    return list_active_categories()


def create_or_update_category(
    name: str,
    description: Optional[str] = None,
    category_id: Optional[int] = None,
) -> Any:
    """
    Crea o aggiorna una categoria.

    - se category_id è fornito, aggiorna quella categoria (se esiste)
    - altrimenti:
        - se esiste già una categoria con lo stesso nome, la aggiorna
        - altrimenti ne crea una nuova
    Esegue commit immediato.
    """
    if category_id is not None:
        category = get_category_by_id(category_id)
    else:
        category = get_category_by_name(name)

    data = {
        "name": name,
        "description": description,
        "is_active": True,
    }

    if category is None:
        category = create_category(**data)
    else:
        update_category(category, **data)

    db.session.commit()
    return category


def assign_category_to_line(line_id: int, category_id: Optional[int]) -> Optional[DocumentLine]:
    """
    Assegna (o rimuove se category_id è None) una categoria a una singola riga documento.

    Esegue commit immediato.
    """
    line = get_document_line_by_id(line_id)
    if line is None:
        return None

    if category_id is None:
        line.category_id = None
    else:
        category = get_category_by_id(category_id)
        if category is None:
            return None
        line.category_id = category.id

    db.session.commit()
    return line


def bulk_assign_category_to_invoice_lines(
    invoice_id: int,
    category_id: Optional[int],
    line_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Assegna (o rimuove) una categoria a più righe dello stesso documento.

    :param invoice_id: ID del documento
    :param category_id: categoria da assegnare, oppure None per rimuovere
    :param line_ids: lista di ID riga da aggiornare; se None, aggiorna tutte le righe
    :return: riepilogo dell'operazione
    """
    lines = list_lines_by_document(invoice_id)
    if line_ids is not None:
        lines = [l for l in lines if l.id in line_ids]

    updated_count = 0

    if category_id is None:
        # Rimuove categoria
        for line in lines:
            line.category_id = None
            updated_count += 1
    else:
        category = get_category_by_id(category_id)
        if category is None:
            return {
                "success": False,
                "message": "Categoria non trovata",
                "updated_count": 0,
            }

        for line in lines:
            line.category_id = category.id
            updated_count += 1

    db.session.commit()

    return {
        "success": True,
        "message": "Categorie aggiornate con successo",
        "updated_count": updated_count,
    }
