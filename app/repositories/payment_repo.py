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

    def get_unpaid_by_document_ids(self, document_ids: List[int]) -> List[Payment]:
        """
        Fetch all unpaid/partial Payment records for given Document IDs.

        Args:
            document_ids: List of Document IDs to query

        Returns:
            List of Payment objects with status IN ('unpaid', 'partial')

        Example:
            >>> repo.get_unpaid_by_document_ids([123, 124, 125])
            [Payment(id=456, document_id=123, status='unpaid'), ...]
        """
        return (
            self.session.query(Payment)
            .filter(
                Payment.document_id.in_(document_ids),
                Payment.status.in_(['unpaid', 'partial'])
            )
            .order_by(Payment.document_id.asc(), Payment.due_date.asc())
            .all()
        )