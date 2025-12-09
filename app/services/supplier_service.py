"""
Servizi per la gestione dei fornitori (Supplier).

Funzioni principali:
- list_suppliers_with_stats() -> elenco fornitori con contatori
- get_supplier_detail(id)     -> dati fornitore + documenti collegati
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models import Document, LegalEntity, Supplier
from app.repositories import (
    get_supplier_by_id,
    list_suppliers,
)
from app.repositories.document_repo import get_supplier_account_balance


def list_suppliers_with_stats() -> List[Dict[str, Any]]:
    """
    Restituisce l'elenco dei fornitori attivi con qualche statistica.
    """
    suppliers = list_suppliers(include_inactive=False)
    results: List[Dict[str, Any]] = []

    for s in suppliers:
        # Conta solo i documenti di tipo invoice per coerenza storica, o tutti?
        # Qui usiamo 'invoices' come property backref se esiste, altrimenti query
        # s.documents include tutto.
        doc_count = len(s.documents) 
        
        total_gross_amount = (
            db.session.query(db.func.coalesce(db.func.sum(Document.total_gross_amount), 0))
            .filter(Document.supplier_id == s.id)
            .scalar()
        )

        results.append(
            {
                "supplier": s,
                "invoice_count": doc_count, # Manteniamo nome chiave per UI
                "total_gross_amount": total_gross_amount,
            }
        )

    return results


def get_supplier_detail(
    supplier_id: int, legal_entity_id: int | None = None
) -> Optional[Dict[str, Any]]:
    """
    Restituisce il dettaglio di un fornitore.
    """
    supplier = get_supplier_by_id(supplier_id)
    if supplier is None:
        return None

    # Query su Document filtrando per tipo 'invoice' per mostrare le fatture
    invoices_query = db.session.query(Document).filter(
        Document.supplier_id == supplier_id,
        Document.document_type == 'invoice'
    ).order_by(
        Document.document_date.desc(), Document.id.desc()
    )

    if legal_entity_id is not None:
        invoices_query = invoices_query.filter(Document.legal_entity_id == legal_entity_id)

    invoices = invoices_query.all()

    account_snapshot = get_supplier_account_balance(
        supplier_id=supplier_id,
        legal_entity_id=legal_entity_id,
    )

    available_legal_entities = (
        db.session.query(
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
        "invoices": invoices, # Passiamo oggetti Document (type=invoice)
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