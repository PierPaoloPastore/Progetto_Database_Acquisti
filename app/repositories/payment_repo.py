"""
Repository specifico per Payment.
Eredita le funzioni base (add, get, list) da SqlAlchemyRepository.
"""
from typing import List
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import joinedload

from app.models import Document, LegalEntity, Payment, PaymentDocument, Supplier
from app.services.payment_method_catalog import (
    PAYMENT_METHOD_LABELS,
    map_payment_method_to_document_type,
    normalize_payment_method_code,
)
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

    def search_paid_history(
        self,
        *,
        q: str | None = None,
        date_from=None,
        date_to=None,
        bank_account_iban: str | None = None,
        payment_method: str | None = None,
    ) -> List[Payment]:
        """Restituisce la cronologia pagamenti con filtri avanzati."""
        query = (
            self.session.query(Payment)
            .join(Document, Payment.document_id == Document.id)
            .outerjoin(Supplier, Document.supplier_id == Supplier.id)
            .outerjoin(LegalEntity, Document.legal_entity_id == LegalEntity.id)
            .outerjoin(PaymentDocument, Payment.payment_document_id == PaymentDocument.id)
            .options(
                joinedload(Payment.document).joinedload(Document.supplier),
                joinedload(Payment.document).joinedload(Document.legal_entity),
                joinedload(Payment.payment_document),
            )
            .filter(Payment.status.in_(["paid", "partial"]))
        )

        if date_from is not None:
            query = query.filter(Payment.paid_date >= date_from)
        if date_to is not None:
            query = query.filter(Payment.paid_date <= date_to)
        if bank_account_iban:
            query = query.filter(PaymentDocument.bank_account_iban == bank_account_iban)
        if payment_method:
            payment_type = map_payment_method_to_document_type(payment_method)
            if payment_type:
                query = query.filter(
                    or_(
                        Payment.payment_method == payment_method,
                        PaymentDocument.payment_type == payment_type,
                    )
                )
            else:
                query = query.filter(Payment.payment_method == payment_method)

        search_text = (q or "").strip()
        if search_text:
            like_value = f"%{search_text}%"
            normalized_code = normalize_payment_method_code(search_text)
            lowered = search_text.lower()
            matching_method_codes = [
                code
                for code, label in PAYMENT_METHOD_LABELS.items()
                if lowered in code.lower() or lowered in label.lower()
            ]

            search_filters = [
                cast(Payment.id, String).ilike(like_value),
                cast(Document.id, String).ilike(like_value),
                Document.document_number.ilike(like_value),
                Supplier.name.ilike(like_value),
                LegalEntity.name.ilike(like_value),
                Payment.notes.ilike(like_value),
                Payment.status.ilike(like_value),
                Payment.payment_method.ilike(like_value),
                cast(Payment.payment_document_id, String).ilike(like_value),
                PaymentDocument.file_name.ilike(like_value),
                PaymentDocument.payment_type.ilike(like_value),
                PaymentDocument.bank_account_iban.ilike(like_value),
                cast(Payment.paid_amount, String).ilike(like_value),
                cast(Payment.expected_amount, String).ilike(like_value),
                func.date_format(Payment.paid_date, "%d/%m/%Y").ilike(like_value),
                func.date_format(Payment.paid_date, "%Y-%m-%d").ilike(like_value),
                func.date_format(Payment.updated_at, "%d/%m/%Y").ilike(like_value),
                func.date_format(Payment.updated_at, "%Y-%m-%d").ilike(like_value),
            ]
            if normalized_code:
                search_filters.append(Payment.payment_method == normalized_code)
            if matching_method_codes:
                search_filters.append(Payment.payment_method.in_(matching_method_codes))
            query = query.filter(or_(*search_filters))

        return query.order_by(Payment.paid_date.desc(), Payment.updated_at.desc(), Payment.id.desc()).all()
