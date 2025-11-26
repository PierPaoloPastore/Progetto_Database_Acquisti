from __future__ import annotations

"""
Repository per il modello Supplier.

Espone funzioni di lettura/scrittura semplici e una utility
"get_or_create_supplier_from_dto" tollerante a DTO sia dict sia dataclass.
"""

import logging
from typing import Iterable, Optional

from app.extensions import db
from app.models import Supplier

logger = logging.getLogger(__name__)


def _get_attr(data: object, name: str) -> Optional[object]:
    """Recupera un attributo da dict o oggetto, restituendo None se assente."""
    if isinstance(data, dict):
        return data.get(name)
    return getattr(data, name, None)


def list_suppliers(include_inactive: bool = True) -> Iterable[Supplier]:
    """Restituisce l'elenco dei fornitori, opzionalmente filtrati per attivi."""
    query = Supplier.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    return query.order_by(Supplier.name.asc()).all()


def get_supplier_by_id(supplier_id: int) -> Optional[Supplier]:
    """Restituisce un fornitore dato il suo ID."""
    return Supplier.query.get(supplier_id)


def get_supplier_by_vat_number(vat_number: Optional[str]) -> Optional[Supplier]:
    """Cerca fornitore per Partita IVA."""
    if not vat_number:
        return None
    return Supplier.query.filter_by(vat_number=vat_number).first()


def get_supplier_by_tax_code(tax_code: Optional[str]) -> Optional[Supplier]:
    """Cerca fornitore per Codice Fiscale."""
    if not tax_code:
        return None
    return Supplier.query.filter_by(tax_code=tax_code).first()


def create_supplier(data: object) -> Supplier:
    """
    Crea un nuovo fornitore e fa flush per avere l'ID immediatamente disponibile.

    `data` può essere un dict o un DTO con attributi compatibili (es. SupplierDTO).
    """
    new_supplier = Supplier(
        name=_get_attr(data, "name"),
        vat_number=_get_attr(data, "vat_number"),
        tax_code=_get_attr(data, "tax_code"),
        sdi_code=_get_attr(data, "sdi_code"),
        pec_email=_get_attr(data, "pec_email"),
        email=_get_attr(data, "email"),
        phone=_get_attr(data, "phone"),
        address=_get_attr(data, "address"),
        postal_code=_get_attr(data, "postal_code"),
        city=_get_attr(data, "city"),
        province=_get_attr(data, "province"),
        country=_get_attr(data, "country") or "IT",
    )
    db.session.add(new_supplier)
    db.session.flush()
    return new_supplier


def update_supplier(supplier: Supplier, **kwargs) -> Supplier:
    """Aggiorna i campi di un fornitore esistente."""
    for key, value in kwargs.items():
        if hasattr(supplier, key):
            setattr(supplier, key, value)
    return supplier


def get_or_create_supplier_from_dto(supplier_dto: object) -> Supplier:
    """
    Logica avanzata per import: cerca per P.IVA o Codice Fiscale, se non esiste crea.

    Il DTO può essere sia un dataclass (SupplierDTO) sia un dizionario.
    Restituisce l'oggetto Supplier già flushato (ID disponibile).
    """
    vat_number = _get_attr(supplier_dto, "vat_number")
    tax_code = _get_attr(supplier_dto, "tax_code") or _get_attr(
        supplier_dto, "fiscal_code"
    )

    supplier: Optional[Supplier] = None

    if vat_number:
        supplier = get_supplier_by_vat_number(vat_number)

    if not supplier and tax_code:
        supplier = get_supplier_by_tax_code(tax_code)

    if not supplier:
        logger.info("Fornitore non trovato, creazione: %s", _get_attr(supplier_dto, "name"))
        supplier = create_supplier(supplier_dto)

    return supplier
