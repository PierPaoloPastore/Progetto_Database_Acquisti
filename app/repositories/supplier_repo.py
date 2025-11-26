# app/repositories/supplier_repo.py

from app.extensions import db
from app.models.supplier import Supplier
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)

def get_all_suppliers():
    """Restituisce tutti i fornitori."""
    return Supplier.query.all()

def get_supplier_by_id(supplier_id):
    """Restituisce un fornitore dato il suo ID."""
    return Supplier.query.get(supplier_id)

def get_supplier_by_vat(vat_number):
    """Cerca fornitore per Partita IVA."""
    if not vat_number:
        return None
    return Supplier.query.filter_by(vat_number=vat_number).first()

def get_supplier_by_fiscal_code(fiscal_code):
    """Cerca fornitore per Codice Fiscale."""
    if not fiscal_code:
        return None
    return Supplier.query.filter_by(fiscal_code=fiscal_code).first()

def create_supplier(data):
    """Crea un nuovo fornitore (senza commit, solo flush)."""
    new_supplier = Supplier(
        name=data.get('name'),
        vat_number=data.get('vat_number'),
        fiscal_code=data.get('fiscal_code'),
        address_street=data.get('address_street'),
        address_zip=data.get('address_zip'),
        address_city=data.get('address_city'),
        address_province=data.get('address_province'),
        country=data.get('country', 'IT'),
        email=data.get('email'),
        phone=data.get('phone')
    )
    db.session.add(new_supplier)
    db.session.flush()
    return new_supplier

def get_or_create_supplier_from_dto(supplier_dto):
    """
    Logica avanzata per import: cerca per P.IVA o CF, 
    se non esiste crea.
    Restituisce l'oggetto Supplier (già flushato, con ID).
    """
    supplier = None
    
    # 1. Cerca per P.IVA se presente
    if supplier_dto.get('vat_number'):
        supplier = get_supplier_by_vat(supplier_dto['vat_number'])
    
    # 2. Se non trovato, cerca per Codice Fiscale se presente
    if not supplier and supplier_dto.get('fiscal_code'):
        supplier = get_supplier_by_fiscal_code(supplier_dto['fiscal_code'])
        
    # 3. Se ancora non trovato, crea
    if not supplier:
        logger.info(f"Fornitore non trovato, creazione: {supplier_dto.get('name')}")
        supplier = create_supplier(supplier_dto)
    
    return supplier