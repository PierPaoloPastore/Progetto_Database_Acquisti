"""
Servizi per la gestione delle intestazioni (LegalEntity).
Rifattorizzato con Pattern Unit of Work.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import or_

from app.extensions import db
from app.models import Document, LegalEntity, Payment, Supplier
from app.services.unit_of_work import UnitOfWork


def list_legal_entities_with_stats(search_term: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Restituisce l'elenco delle intestazioni con statistiche.
    Consente filtraggio per nome, P.IVA o CF.
    """
    with UnitOfWork() as uow:
        query = uow.session.query(LegalEntity)
        if search_term:
            term = f"%{search_term.strip()}%"
            query = query.filter(
                or_(
                    LegalEntity.name.ilike(term),
                    LegalEntity.vat_number.ilike(term),
                    LegalEntity.fiscal_code.ilike(term),
                )
            )
        entities = query.order_by(LegalEntity.name.asc()).all()

        results: List[Dict[str, Any]] = []
        for entity in entities:
            doc_count = len(entity.documents)
            total_gross = (
                uow.session.query(db.func.sum(Document.total_gross_amount))
                .filter(Document.legal_entity_id == entity.id)
                .scalar()
                or 0
            )
            results.append(
                {
                    "legal_entity": entity,
                    "document_count": doc_count,
                    "total_gross_amount": total_gross,
                }
            )

        return results


def get_legal_entity_detail(
    legal_entity_id: int, supplier_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Restituisce il dettaglio di una intestazione + documenti e snapshot.
    """
    with UnitOfWork() as uow:
        entity = uow.session.get(LegalEntity, legal_entity_id)
        if entity is None:
            return None

        documents_query = (
            uow.session.query(Document)
            .filter(Document.legal_entity_id == legal_entity_id)
            .order_by(Document.document_date.desc(), Document.id.desc())
        )
        if supplier_id is not None:
            documents_query = documents_query.filter(Document.supplier_id == supplier_id)

        documents = documents_query.all()

        account_snapshot = _get_legal_entity_account_snapshot(
            uow, legal_entity_id, supplier_id
        )

        available_suppliers = (
            uow.session.query(
                Supplier.id,
                Supplier.name,
                db.func.count(Document.id).label("document_count"),
            )
            .outerjoin(
                Document,
                (Document.supplier_id == Supplier.id)
                & (Document.legal_entity_id == legal_entity_id),
            )
            .group_by(Supplier.id)
            .order_by(Supplier.name.asc())
            .all()
        )

        return {
            "legal_entity": entity,
            "documents": documents,
            "available_suppliers": [
                {
                    "id": supplier_id,
                    "name": supplier_name,
                    "document_count": document_count,
                }
                for supplier_id, supplier_name, document_count in available_suppliers
            ],
            "selected_supplier_id": supplier_id,
            "account_snapshot": account_snapshot,
        }


def update_legal_entity(
    legal_entity_id: int,
    *,
    name: Optional[str] = None,
    vat_number: Optional[str] = None,
    fiscal_code: Optional[str] = None,
    address: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    is_active: Optional[str] = None,
) -> Optional[LegalEntity]:
    """Aggiorna i campi base di una intestazione."""
    with UnitOfWork() as uow:
        entity = uow.session.get(LegalEntity, legal_entity_id)
        if not entity:
            return None

        def _clean(val: Optional[str]) -> Optional[str]:
            if val is None:
                return None
            val = val.strip()
            return val or None

        if name is not None and name.strip():
            entity.name = name.strip()

        cleaned_vat = _clean(vat_number)
        if cleaned_vat is not None:
            entity.vat_number = cleaned_vat

        entity.fiscal_code = _clean(fiscal_code)
        entity.address = _clean(address)
        entity.city = _clean(city)
        entity.country = _clean(country)

        if is_active is not None:
            entity.is_active = _parse_bool(is_active)

        uow.commit()
        return entity


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_legal_entity_account_snapshot(
    uow: UnitOfWork, legal_entity_id: int, supplier_id: Optional[int]
) -> Dict[str, Any]:
    query = (
        uow.session.query(
            db.func.coalesce(db.func.sum(Document.total_gross_amount), 0),
            db.func.coalesce(db.func.sum(Payment.paid_amount), 0),
            db.func.count(db.func.distinct(Document.id)),
        )
        .select_from(Document)
        .outerjoin(Payment, Payment.document_id == Document.id)
        .filter(Document.legal_entity_id == legal_entity_id)
    )
    if supplier_id is not None:
        query = query.filter(Document.supplier_id == supplier_id)

    expected_total, paid_total, doc_count = query.one()
    residual = expected_total - paid_total

    return {
        "expected_total": expected_total,
        "paid_total": paid_total,
        "residual": residual,
        "document_count": doc_count,
    }
