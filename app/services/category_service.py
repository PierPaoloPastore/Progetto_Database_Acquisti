"""
Servizi per la gestione delle categorie (Category) e assegnazione alle righe documento.
Rifattorizzato con Pattern Unit of Work.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Importiamo la Unit of Work
from app.services.unit_of_work import UnitOfWork

# Importiamo funzioni ausiliarie per le Righe Documento (che non sono ancora sotto UoW completa)
# Nota: In un refactoring completo, anche queste dovrebbero passare per un Repository nel UoW.
from app.repositories import (
    get_document_line_by_id,
    list_lines_by_document,
)

def list_categories_for_ui() -> List:
    """
    Restituisce tutte le categorie attive, ordinate per nome.
    """
    with UnitOfWork() as uow:
        # Nota: usiamo list_active() definito nel nostro nuovo repository
        return uow.categories.list_active()


def list_all_categories() -> List:
    """
    Restituisce tutte le categorie (attive e non), ordinate per nome.
    """
    with UnitOfWork() as uow:
        return uow.categories.list_all_ordered()


def create_or_update_category(
    name: str,
    description: Optional[str] = None,
    vat_rate: Optional[float] = None,
    category_id: Optional[int] = None,
) -> Any:
    """
    Crea o aggiorna una categoria usando UoW.
    """
    with UnitOfWork() as uow:
        category = None
        
        # 1. Recupero entità esistente (se c'è ID o Nome)
        if category_id is not None:
            category = uow.categories.get_by_id(category_id)
        else:
            category = uow.categories.get_by_name(name)

        # 2. Logica di creazione o aggiornamento
        if category is None:
            # Creazione
            # Nota: Istanziamo il modello qui (o potremmo delegarlo al repo, ma meglio qui per chiarezza)
            from app.models import Category
            category = Category(
                name=name,
                description=description,
                vat_rate=vat_rate,
                is_active=True
            )
            uow.categories.add(category)
        else:
            # Aggiornamento
            category.name = name
            category.description = description
            category.vat_rate = vat_rate
            # Non serve chiamare 'update', SQLAlchemy traccia le modifiche automaticamente
            # fintanto che l'oggetto è nella sessione.

        # 3. Commit della transazione
        uow.commit()
        
        # Ritorniamo l'oggetto (che sarà "detached" o "expired" dopo il commit, 
        # ma i dati base dovrebbero essere leggibili se la sessione non è chiusa aggressivamente,
        # oppure ritorniamo i dati. Per sicurezza in Flask solitamente va bene ritornare l'oggetto).
        return category


def set_category_active(category_id: int, is_active: bool) -> Optional[Any]:
    """
    Attiva/disattiva una categoria senza eliminarla (evita orfani).
    """
    with UnitOfWork() as uow:
        category = uow.categories.get_by_id(category_id)
        if category is None:
            return None
        category.is_active = bool(is_active)
        uow.commit()
        return category


def assign_category_to_line(line_id: int, category_id: Optional[int]) -> Any:
    """
    Assegna una categoria a una riga.
    """
    with UnitOfWork() as uow:
        # Recuperiamo la riga (ancora col vecchio metodo, ma usa la stessa db.session sottostante)
        line = get_document_line_by_id(line_id)
        if line is None:
            return None

        if category_id is None:
            line.category_id = None
        else:
            # Verifica esistenza categoria tramite UoW
            category = uow.categories.get_by_id(category_id)
            if category is None:
                return None
            line.category_id = category.id

        uow.commit()
        return line


def bulk_assign_category_to_invoice_lines(
    invoice_id: int,
    category_id: Optional[int],
    line_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Assegna massivamente categorie.
    """
    with UnitOfWork() as uow:
        # Recupero righe (vecchio metodo)
        lines = list_lines_by_document(invoice_id)
        
        # Filtro se necessario
        if line_ids is not None:
            lines = [l for l in lines if l.id in line_ids]

        updated_count = 0
        target_cat_id = None

        if category_id is not None:
            category = uow.categories.get_by_id(category_id)
            if category is None:
                return {
                    "success": False,
                    "message": "Categoria non trovata",
                    "updated_count": 0,
                }
            target_cat_id = category.id

        # Loop di aggiornamento
        for line in lines:
            line.category_id = target_cat_id
            updated_count += 1

        uow.commit()

        return {
            "success": True,
            "message": "Categorie aggiornate con successo",
            "updated_count": updated_count,
        }

def predict_category_for_line(description: str) -> Optional[int]:
    """
    PLACEHOLDER per futura implementazione AI/ML.
    """
    # TODO: In futuro, integrare qui logica Fuzzy Matching o ML Model
    return None
