"""
Repository specifico per Supplier.
Eredita le funzioni base (add, get, list) da SqlAlchemyRepository.
"""
from typing import Optional, List, Any
import logging

from app.models import Supplier
from app.repositories.base import SqlAlchemyRepository

logger = logging.getLogger(__name__)

class SupplierRepository(SqlAlchemyRepository[Supplier]):
    def __init__(self, session):
        super().__init__(session, Supplier)

    def get_by_vat_number(self, vat_number: str) -> Optional[Supplier]:
        """Cerca fornitore per Partita IVA esatta."""
        if not vat_number:
            return None
        return self.session.query(Supplier).filter_by(vat_number=vat_number).first()

    def get_by_fiscal_code(self, fiscal_code: str) -> Optional[Supplier]:
        """Cerca fornitore per Codice Fiscale esatto."""
        if not fiscal_code:
            return None
        return self.session.query(Supplier).filter_by(fiscal_code=fiscal_code).first()

    def list_active(self) -> List[Supplier]:
        """Restituisce l'elenco dei fornitori attivi ordinati per nome."""
        return (
            self.session.query(Supplier)
            .filter_by(is_active=True)
            .order_by(Supplier.name.asc())
            .all()
        )
    
    def list_all_ordered(self) -> List[Supplier]:
        """Restituisce tutti i fornitori ordinati per nome."""
        return self.session.query(Supplier).order_by(Supplier.name.asc()).all()

    def get_or_create_from_dto(self, data: Any) -> Supplier:
        """
        Cerca un fornitore per P.IVA o CF. Se non esiste, lo crea.
        Gestisce sia dict che oggetti DTO.
        Esegue flush automatico per avere l'ID disponibile.
        """
        # Helper interno per estrarre attributi da dict o oggetto
        def _get(obj, name):
            if isinstance(obj, dict):
                return obj.get(name)
            return getattr(obj, name, None)

        vat_number = _get(data, "vat_number")
        fiscal_code = _get(data, "fiscal_code")
        name = _get(data, "name")

        supplier: Optional[Supplier] = None

        if vat_number:
            supplier = self.get_by_vat_number(vat_number)
        
        if not supplier and fiscal_code:
            supplier = self.get_by_fiscal_code(fiscal_code)

        if not supplier:
            logger.info("Fornitore non trovato, creazione: %s", name)
            supplier = Supplier(
                name=name,
                vat_number=vat_number,
                fiscal_code=fiscal_code,
                sdi_code=_get(data, "sdi_code"),
                pec_email=_get(data, "pec_email"),
                email=_get(data, "email"),
                phone=_get(data, "phone"),
                address=_get(data, "address"),
                postal_code=_get(data, "postal_code"),
                city=_get(data, "city"),
                province=_get(data, "province"),
                country=_get(data, "country") or "IT",
                is_active=True
            )
            self.add(supplier)
            # Flush per ottenere l'ID se serve subito dopo nella transazione
            self.session.flush()

        return supplier