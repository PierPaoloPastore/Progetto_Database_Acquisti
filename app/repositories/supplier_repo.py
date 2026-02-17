"""
Repository specifico per Supplier.
Eredita le funzioni base (add, get, list) da SqlAlchemyRepository.
"""
from typing import Optional, List, Any
import logging

from app.models import Supplier
from app.repositories.base import SqlAlchemyRepository
from sqlalchemy import or_

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

    def get_by_vat_and_fiscal(self, vat_number: str, fiscal_code: str) -> Optional[Supplier]:
        """Cerca fornitore per combinazione P.IVA + CF."""
        if not vat_number or not fiscal_code:
            return None
        return (
            self.session.query(Supplier)
            .filter(Supplier.vat_number == vat_number, Supplier.fiscal_code == fiscal_code)
            .first()
        )

    def list_by_vat_number(self, vat_number: str) -> List[Supplier]:
        """Restituisce tutti i fornitori con la stessa P.IVA (ordinati per id)."""
        if not vat_number:
            return []
        return (
            self.session.query(Supplier)
            .filter(Supplier.vat_number == vat_number)
            .order_by(Supplier.id.asc())
            .all()
        )

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

    def search_active(self, term: Optional[str]) -> List[Supplier]:
        """
        Cerca fornitori attivi per nome, P.IVA o CF (case-insensitive).
        Se term è vuoto, restituisce la lista attiva completa.
        """
        if not term or not term.strip():
            return self.list_active()

        pattern = f"%{term.strip()}%"
        return (
            self.session.query(Supplier)
            .filter(
                Supplier.is_active.is_(True),
                or_(
                    Supplier.name.ilike(pattern),
                    Supplier.vat_number.ilike(pattern),
                    Supplier.fiscal_code.ilike(pattern),
                ),
            )
            .order_by(Supplier.name.asc())
            .all()
        )

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

        def _clean(value):
            if value is None:
                return None
            cleaned = str(value).strip()
            return cleaned or None

        def _normalize_iban(value):
            cleaned = _clean(value)
            if not cleaned:
                return None
            return "".join(cleaned.split()).upper()

        vat_number = _clean(_get(data, "vat_number"))
        fiscal_code = _clean(_get(data, "fiscal_code"))
        name = _clean(_get(data, "name"))
        iban = _normalize_iban(_get(data, "iban"))

        supplier: Optional[Supplier] = None

        if vat_number and fiscal_code:
            supplier = self.get_by_vat_and_fiscal(vat_number, fiscal_code)
            if not supplier:
                # Se esiste un record con P.IVA uguale ma CF mancante, aggiorniamo quel record
                candidate = (
                    self.session.query(Supplier)
                    .filter(
                        Supplier.vat_number == vat_number,
                        or_(Supplier.fiscal_code.is_(None), Supplier.fiscal_code == ""),
                    )
                    .first()
                )
                if candidate:
                    candidate.fiscal_code = fiscal_code
                    supplier = candidate

        if not supplier and vat_number and not fiscal_code:
            candidates = self.list_by_vat_number(vat_number)
            if len(candidates) == 1:
                supplier = candidates[0]
            elif candidates:
                blank_cf = next((s for s in candidates if not (s.fiscal_code or "").strip()), None)
                supplier = blank_cf or candidates[0]

        if not supplier and fiscal_code:
            supplier = self.get_by_fiscal_code(fiscal_code)

        if not supplier:
            logger.info("Fornitore non trovato, creazione: %s", name)
            typical_due_rule = _get(data, "typical_due_rule") or "end_of_month"
            typical_due_days = _get(data, "typical_due_days")
            supplier = Supplier(
                name=name,
                vat_number=vat_number,
                fiscal_code=fiscal_code,
                sdi_code=_get(data, "sdi_code"),
                pec_email=_get(data, "pec_email"),
                email=_get(data, "email"),
                iban=iban,
                phone=_get(data, "phone"),
                address=_get(data, "address"),
                postal_code=_get(data, "postal_code"),
                city=_get(data, "city"),
                province=_get(data, "province"),
                country=_get(data, "country") or "IT",
                typical_due_rule=typical_due_rule,
                typical_due_days=typical_due_days,
                is_active=True
            )
            self.add(supplier)
            # Flush per ottenere l'ID se serve subito dopo nella transazione
            self.session.flush()
        elif iban and not (supplier.iban or "").strip():
            supplier.iban = iban

        return supplier
