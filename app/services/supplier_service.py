"""
Servizi per la gestione dei fornitori (Supplier).
Rifattorizzato con Pattern Unit of Work.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models import Document, LegalEntity, Supplier
from app.services.unit_of_work import UnitOfWork

def list_active_suppliers() -> List[Supplier]:
    """
    Restituisce l'elenco dei fornitori attivi (per dropdown/filtri).
    """
    with UnitOfWork() as uow:
        return uow.suppliers.list_active()


def list_suppliers_with_stats() -> List[Dict[str, Any]]:
    """
    Restituisce l'elenco dei fornitori attivi con statistiche.
    """
    with UnitOfWork() as uow:
        # 1. Recupera fornitori attivi dal repo
        suppliers = uow.suppliers.list_active()
        results: List[Dict[str, Any]] = []

        # 2. Arricchisce con statistiche (query legacy usando la sessione UoW)
        for s in suppliers:
            # Nota: s.documents usa la sessione corrente per il lazy loading
            doc_count = len(s.documents)
            
            # Query manuale
            total_gross = uow.session.query(db.func.sum(Document.total_gross_amount))\
                .filter(Document.supplier_id == s.id).scalar() or 0

            results.append({
                "supplier": s,
                "invoice_count": doc_count,
                "total_gross_amount": total_gross,
            })

        return results


def get_supplier_detail(
    supplier_id: int, legal_entity_id: int | None = None
) -> Optional[Dict[str, Any]]:
    """
    Restituisce il dettaglio di un fornitore + fatture e snapshot.
    """
    with UnitOfWork() as uow:
        supplier = uow.suppliers.get_by_id(supplier_id)
        if supplier is None:
            return None

        # Query Documenti (type=invoice)
        invoices_query = uow.session.query(Document).filter(
            Document.supplier_id == supplier_id,
            Document.document_type == 'invoice'
        ).order_by(Document.document_date.desc(), Document.id.desc())

        if legal_entity_id is not None:
            invoices_query = invoices_query.filter(Document.legal_entity_id == legal_entity_id)

        invoices = invoices_query.all()

        # FIX: Usa il metodo del repository Documents invece della funzione importata
        account_snapshot = uow.documents.get_supplier_account_balance(
            supplier_id=supplier_id,
            legal_entity_id=legal_entity_id,
        )

        # Query Available Legal Entities
        available_legal_entities = (
            uow.session.query(
                LegalEntity.id,
                LegalEntity.name,
                db.func.count(Document.id).label("invoice_count"),
            )
            .outerjoin(
                Document,
                (Document.legal_entity_id == LegalEntity.id)
                & (Document.supplier_id == supplier_id),
            )
            .filter(LegalEntity.is_active.is_(True))
            .group_by(LegalEntity.id)
            .order_by(LegalEntity.name.asc())
            .all()
        )

        return {
            "supplier": supplier,
            "invoices": invoices,
            "available_legal_entities": [
                {
                    "id": le_id,
                    "name": le_name,
                    "invoice_count": invoice_count,
                }
                for le_id, le_name, invoice_count in available_legal_entities
            ],
            "selected_legal_entity_id": legal_entity_id,
            "account_snapshot": account_snapshot,
        }