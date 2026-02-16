"""
Repository per il modello BankAccount.
"""
from typing import List, Optional

from app.models import BankAccount
from app.repositories.base import SqlAlchemyRepository


class BankAccountRepository(SqlAlchemyRepository[BankAccount]):
    def __init__(self, session):
        super().__init__(session, BankAccount)

    def get_by_iban(self, iban: str) -> Optional[BankAccount]:
        return (
            self.session.query(BankAccount)
            .filter(BankAccount.iban == iban)
            .first()
        )

    def list_by_legal_entity(self, legal_entity_id: int) -> List[BankAccount]:
        return (
            self.session.query(BankAccount)
            .filter(BankAccount.legal_entity_id == legal_entity_id)
            .order_by(BankAccount.name.asc())
            .all()
        )

    def list_all_ordered(self) -> List[BankAccount]:
        return (
            self.session.query(BankAccount)
            .order_by(BankAccount.legal_entity_id.asc(), BankAccount.name.asc())
            .all()
        )
