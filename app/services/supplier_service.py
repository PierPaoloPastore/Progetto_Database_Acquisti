"""
Servizi per la gestione dei fornitori (Supplier).
Rifattorizzato con Pattern Unit of Work.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re

from sqlalchemy import func

from app.extensions import db
from app.models import Document, LegalEntity, Supplier
from app.services.unit_of_work import UnitOfWork

def list_active_suppliers() -> List[Supplier]:
    """
    Restituisce l'elenco dei fornitori attivi (per dropdown/filtri).
    """
    with UnitOfWork() as uow:
        return uow.suppliers.list_active()


def list_all_suppliers() -> List[Supplier]:
    """
    Restituisce l'elenco completo dei fornitori (attivi + inattivi).
    """
    with UnitOfWork() as uow:
        return uow.suppliers.list_all_ordered()


def list_suppliers_with_stats(search_term: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Restituisce l'elenco dei fornitori attivi con statistiche.
    Consente filtraggio per nome, P.IVA o CF.
    """
    with UnitOfWork() as uow:
        # 1. Recupera fornitori attivi dal repo (con filtro opzionale)
        suppliers = uow.suppliers.search_active(search_term)
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


def create_supplier(
    *,
    name: Optional[str],
    vat_number: Optional[str] = None,
    fiscal_code: Optional[str] = None,
    sdi_code: Optional[str] = None,
    pec_email: Optional[str] = None,
    email: Optional[str] = None,
    iban: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    postal_code: Optional[str] = None,
    city: Optional[str] = None,
    province: Optional[str] = None,
    country: Optional[str] = None,
) -> Tuple[Optional[Supplier], Optional[str]]:
    """Crea manualmente un nuovo fornitore con validazioni di base."""
    cleaned_name = _clean_text(name)
    if not cleaned_name:
        return None, "La ragione sociale del fornitore è obbligatoria."

    cleaned_vat = _clean_text(vat_number)
    cleaned_fiscal = _clean_text(fiscal_code)
    cleaned_sdi = _clean_text(sdi_code)
    cleaned_pec = _clean_text(pec_email)
    cleaned_email = _clean_text(email)
    cleaned_iban = _normalize_iban(iban)
    cleaned_phone = _clean_text(phone)
    cleaned_address = _clean_text(address)
    cleaned_postal_code = _clean_text(postal_code)
    cleaned_city = _clean_text(city)
    cleaned_province = _clean_text(province)
    cleaned_country = _clean_text(country) or "IT"

    with UnitOfWork() as uow:
        duplicate_error = _validate_supplier_uniqueness(
            uow=uow,
            name=cleaned_name,
            vat_number=cleaned_vat,
            fiscal_code=cleaned_fiscal,
        )
        if duplicate_error:
            return None, duplicate_error

        supplier = Supplier(
            name=cleaned_name,
            vat_number=cleaned_vat,
            fiscal_code=cleaned_fiscal,
            sdi_code=cleaned_sdi,
            pec_email=cleaned_pec,
            email=cleaned_email,
            iban=cleaned_iban,
            phone=cleaned_phone,
            address=cleaned_address,
            postal_code=cleaned_postal_code,
            city=cleaned_city,
            province=cleaned_province,
            country=cleaned_country,
            typical_due_rule="end_of_month",
            is_active=True,
        )
        uow.suppliers.add(supplier)
        uow.session.flush()
        uow.commit()
        return supplier, None


def update_supplier(
    supplier_id: int,
    *,
    name: Optional[str] = None,
    vat_number: Optional[str] = None,
    fiscal_code: Optional[str] = None,
    sdi_code: Optional[str] = None,
    pec_email: Optional[str] = None,
    email: Optional[str] = None,
    iban: Optional[str] = None,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    postal_code: Optional[str] = None,
    city: Optional[str] = None,
    province: Optional[str] = None,
    country: Optional[str] = None,
    typical_due_rule: Optional[str] = None,
    typical_due_days: Optional[int] = None,
    is_active: Optional[bool | str] = None,
) -> Optional[Supplier]:
    """Aggiorna campi base di un fornitore."""
    with UnitOfWork() as uow:
        supplier = uow.suppliers.get_by_id(supplier_id)
        if not supplier:
            return None

        def _clean(val: Optional[str]) -> Optional[str]:
            if val is None:
                return None
            val = val.strip()
            return val or None

        def _normalize_iban(val: Optional[str]) -> Optional[str]:
            cleaned = _clean(val)
            if not cleaned:
                return None
            return re.sub(r"\s+", "", cleaned).upper()

        def _validate_rule(rule: Optional[str]) -> Optional[str]:
            allowed = {"end_of_month", "net_30", "net_60", "immediate", "next_month_day_1"}
            if not rule:
                return None
            rule = rule.strip()
            return rule if rule in allowed else None

        def _validate_days(raw: Optional[int | str]) -> Optional[int]:
            if raw in (None, ""):
                return None
            try:
                days = int(raw)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
            if days < 0 or days > 365:
                return None
            return days

        def _parse_bool(raw: Optional[bool | str]) -> Optional[bool]:
            if raw is None:
                return None
            if isinstance(raw, bool):
                return raw
            raw_str = str(raw).strip().lower()
            if raw_str in {"1", "true", "yes", "on"}:
                return True
            if raw_str in {"0", "false", "no", "off"}:
                return False
            return None

        if name is not None:
            supplier.name = name.strip()
        supplier.vat_number = _clean(vat_number)
        supplier.fiscal_code = _clean(fiscal_code)
        supplier.sdi_code = _clean(sdi_code)
        supplier.pec_email = _clean(pec_email)
        supplier.email = _clean(email)
        supplier.iban = _normalize_iban(iban)
        supplier.phone = _clean(phone)
        supplier.address = _clean(address)
        supplier.postal_code = _clean(postal_code)
        supplier.city = _clean(city)
        supplier.province = _clean(province)
        supplier.country = _clean(country)

        # Regola scadenza tipica
        supplier.typical_due_rule = _validate_rule(typical_due_rule)
        supplier.typical_due_days = _validate_days(typical_due_days)
        active_flag = _parse_bool(is_active)
        if active_flag is not None:
            supplier.is_active = active_flag

        uow.commit()
        return supplier


def _clean_text(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    cleaned = val.strip()
    return cleaned or None


def _normalize_iban(val: Optional[str]) -> Optional[str]:
    cleaned = _clean_text(val)
    if not cleaned:
        return None
    return re.sub(r"\s+", "", cleaned).upper()


def _validate_supplier_uniqueness(
    *,
    uow: UnitOfWork,
    name: str,
    vat_number: Optional[str],
    fiscal_code: Optional[str],
) -> Optional[str]:
    if vat_number and fiscal_code:
        existing = uow.suppliers.get_by_vat_and_fiscal(vat_number, fiscal_code)
        if existing:
            return f"Esiste già un fornitore con la stessa P.IVA e CF: {existing.name}."

    if fiscal_code:
        existing_by_fiscal = uow.suppliers.get_by_fiscal_code(fiscal_code)
        if existing_by_fiscal:
            return f"Esiste già un fornitore con lo stesso codice fiscale: {existing_by_fiscal.name}."

    if vat_number and not fiscal_code:
        existing_by_vat = uow.suppliers.list_by_vat_number(vat_number)
        if existing_by_vat:
            return (
                "Esiste già almeno un fornitore con questa P.IVA. "
                "Inserisci anche il codice fiscale oppure aggiorna un record esistente."
            )

    existing_by_name = (
        uow.session.query(Supplier)
        .filter(func.lower(Supplier.name) == name.lower())
        .first()
    )
    if existing_by_name and not vat_number and not fiscal_code:
        return f"Esiste già un fornitore con la stessa ragione sociale: {existing_by_name.name}."

    return None
