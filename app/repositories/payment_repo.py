"""
Repository specifico per Payment.
Eredita le funzioni base (add, get, list) da SqlAlchemyRepository.
"""
from typing import List
from app.models import Payment
from app.repositories.base import SqlAlchemyRepository

class PaymentRepository(SqlAlchemyRepository[Payment]):
    def __init__(self, session):
        super().__init__(session, Payment)

    def get_by_document_id(self, document_id: int) -> List[Payment]:
        """Restituisce tutti i pagamenti associati a un documento."""
        return (
            self.session.query(Payment)
            .filter_by(document_id=document_id)
            .order_by(Payment.due_date.asc())
            .all()
        )
    
    def list_all_ordered(self) -> List[Payment]:
        """Restituisce tutti i pagamenti ordinati per data decrescente."""
        return (
            self.session.query(Payment)
            .order_by(Payment.due_date.desc())
            .all()
        )