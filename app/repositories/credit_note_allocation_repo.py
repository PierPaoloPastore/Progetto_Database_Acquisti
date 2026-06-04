from __future__ import annotations

from decimal import Decimal
from typing import Dict, List

from sqlalchemy import func

from app.models import CreditNoteAllocation
from app.repositories.base import SqlAlchemyRepository


class CreditNoteAllocationRepository(SqlAlchemyRepository[CreditNoteAllocation]):
    def __init__(self, session):
        super().__init__(session, CreditNoteAllocation)

    def list_by_credit_note_id(self, document_id: int) -> List[CreditNoteAllocation]:
        return (
            self.session.query(CreditNoteAllocation)
            .filter(CreditNoteAllocation.credit_note_document_id == document_id)
            .order_by(CreditNoteAllocation.allocated_at.asc(), CreditNoteAllocation.id.asc())
            .all()
        )

    def list_by_invoice_id(self, document_id: int) -> List[CreditNoteAllocation]:
        return (
            self.session.query(CreditNoteAllocation)
            .filter(CreditNoteAllocation.invoice_document_id == document_id)
            .order_by(CreditNoteAllocation.allocated_at.asc(), CreditNoteAllocation.id.asc())
            .all()
        )

    def get_allocated_totals_by_credit_note_ids(self, document_ids: List[int]) -> Dict[int, Decimal]:
        if not document_ids:
            return {}
        rows = (
            self.session.query(
                CreditNoteAllocation.credit_note_document_id,
                func.coalesce(func.sum(CreditNoteAllocation.allocated_amount), 0),
            )
            .filter(CreditNoteAllocation.credit_note_document_id.in_(document_ids))
            .group_by(CreditNoteAllocation.credit_note_document_id)
            .all()
        )
        return {document_id: Decimal(total or 0) for document_id, total in rows}

    def get_allocated_totals_by_invoice_ids(self, document_ids: List[int]) -> Dict[int, Decimal]:
        if not document_ids:
            return {}
        rows = (
            self.session.query(
                CreditNoteAllocation.invoice_document_id,
                func.coalesce(func.sum(CreditNoteAllocation.allocated_amount), 0),
            )
            .filter(CreditNoteAllocation.invoice_document_id.in_(document_ids))
            .group_by(CreditNoteAllocation.invoice_document_id)
            .all()
        )
        return {document_id: Decimal(total or 0) for document_id, total in rows}
