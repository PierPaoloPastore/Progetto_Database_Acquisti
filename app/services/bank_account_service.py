"""
Servizi per la gestione dei conti bancari (BankAccount).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from app.models import BankAccount, LegalEntity
from app.services.unit_of_work import UnitOfWork


def normalize_iban(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return "".join(raw.split()).upper()


def list_bank_accounts_by_legal_entity(legal_entity_id: int) -> List[BankAccount]:
    with UnitOfWork() as uow:
        return uow.bank_accounts.list_by_legal_entity(legal_entity_id)


def list_all_bank_accounts() -> List[BankAccount]:
    with UnitOfWork() as uow:
        return uow.bank_accounts.list_all_ordered()


def create_bank_account(
    legal_entity_id: int,
    *,
    iban: Optional[str],
    name: Optional[str],
    notes: Optional[str],
) -> Tuple[Optional[BankAccount], Optional[str]]:
    cleaned_iban = normalize_iban(iban)
    cleaned_name = (name or "").strip()
    cleaned_notes = (notes or "").strip() or None

    if not cleaned_iban:
        return None, "IBAN obbligatorio."
    if not cleaned_name:
        return None, "Nome conto obbligatorio."

    with UnitOfWork() as uow:
        entity = uow.session.get(LegalEntity, legal_entity_id)
        if not entity:
            return None, "Intestazione non trovata."

        existing = uow.bank_accounts.get_by_iban(cleaned_iban)
        if existing:
            return None, "IBAN già presente. Usa un IBAN diverso."

        account = BankAccount(
            iban=cleaned_iban,
            legal_entity_id=legal_entity_id,
            name=cleaned_name,
            notes=cleaned_notes,
        )
        uow.bank_accounts.add(account)
        uow.commit()
        return account, None
