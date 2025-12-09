"""
Servizi per la gestione dei fornitori (Supplier).

Funzioni principali:
- list_suppliers_with_stats() -> elenco fornitori con contatori
- get_supplier_detail(id)     -> dati fornitore + fatture collegate
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models import Invoice, LegalEntity, Supplier
from app.repositories import (
    get_supplier_by_id,
    list_suppliers,
)
from app.repositories.invoice_repo import get_supplier_account_balance


def list_suppliers_with_stats() -> List[Dict[str, Any]]:
    """
    Restituisce l'elenco dei fornitori attivi con qualche statistica,
    utile per la UI (es. elenco fornitori).

    Output tipo:
    [
      {
        "supplier": Supplier,
        "invoice_count": int,
        "total_gross_amount": Decimal,
      },
      ...
    ]
    """
    suppliers = list_suppliers(include_inactive=False)
    results: List[Dict[str, Any]] = []

    for s in suppliers:
        invoice_count = len(s.invoices)
        total_gross_amount = (
            db.session.query(db.func.coalesce(db.func.sum(Invoice.total_gross_amount), 0))
            .filter(Invoice.supplier_id == s.id)
            .scalar()
        )

        results.append(
            {
                "supplier": s,
                "invoice_count": invoice_count,
                "total_gross_amount": total_gross_amount,
            }
        )

    return results


def get_supplier_detail(
    supplier_id: int, legal_entity_id: int | None = None
) -> Optional[Dict[str, Any]]:
    """
    Restituisce il dettaglio di un fornitore, opzionalmente filtrando per legal entity:

    {
      "supplier": Supplier,
      "invoices": [Invoice, ...],
      "available_legal_entities": [
          {"id": int, "name": str, "invoice_count": int}, ...
      ],
      "selected_legal_entity_id": int | None,
      "account_snapshot": {expected_total, paid_total, residual, invoice_count},
    }

    Restituisce None se il fornitore non esiste.
    """
    supplier = get_supplier_by_id(supplier_id)
    if supplier is None:
        return None

    invoices_query = supplier.documents.filter_by(document_type='invoice').order_by(
        Invoice.document_date.desc(), Invoice.id.desc()
    )

    if legal_entity_id is not None:
        invoices_query = invoices_query.filter(Invoice.legal_entity_id == legal_entity_id)

    invoices = invoices_query.all()

    account_snapshot = get_supplier_account_balance(
        supplier_id=supplier_id,
        legal_entity_id=legal_entity_id,
    )

    available_legal_entities = (
        db.session.query(
            LegalEntity.id,
            LegalEntity.name,
            db.func.count(Invoice.id).label("invoice_count"),
        )
        .outerjoin(
            Invoice,
            (Invoice.legal_entity_id == LegalEntity.id)
            & (Invoice.supplier_id == supplier_id),
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
