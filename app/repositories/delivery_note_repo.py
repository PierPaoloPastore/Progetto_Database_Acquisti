"""
Repository specifico per DeliveryNote.
Gestisce query e operazioni di base sui DDT.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import joinedload
from sqlalchemy import or_

from app.models import DeliveryNote
from app.repositories.base import SqlAlchemyRepository


class DeliveryNoteRepository(SqlAlchemyRepository[DeliveryNote]):
    def __init__(self, session):
        super().__init__(session, DeliveryNote)

    def get_by_id(self, note_id: int) -> Optional[DeliveryNote]:
        return (
            self.session.query(DeliveryNote)
            .options(
                joinedload(DeliveryNote.supplier),
                joinedload(DeliveryNote.legal_entity),
            )
            .get(note_id)
        )

    def list_for_ui(
        self,
        search_term: Optional[str] = None,
        supplier_id: Optional[int] = None,
        legal_entity_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> List[DeliveryNote]:
        """
        Restituisce DDT per la UI, con join su fornitore/intestatario.
        Filtri semplici su testo (numero) e anagrafiche.
        """
        query = (
            self.session.query(DeliveryNote)
            .options(
                joinedload(DeliveryNote.supplier),
                joinedload(DeliveryNote.legal_entity),
            )
            .order_by(DeliveryNote.ddt_date.desc(), DeliveryNote.id.desc())
        )

        if search_term:
            like = f"%{search_term}%"
            query = query.filter(
                or_(
                    DeliveryNote.ddt_number.ilike(like),
                    DeliveryNote.file_name.ilike(like),
                )
            )

        if supplier_id:
            query = query.filter(DeliveryNote.supplier_id == supplier_id)
        if legal_entity_id:
            query = query.filter(DeliveryNote.legal_entity_id == legal_entity_id)
        if status:
            query = query.filter(DeliveryNote.status == status)

        return query.limit(limit).all()

    def find_candidates_for_match(
        self,
        supplier_id: int,
        ddt_number: Optional[str] = None,
        ddt_date: Optional[date] = None,
        allowed_statuses: Optional[List[str]] = None,
        limit: int = 200,
        exclude_document_ids: Optional[List[int]] = None,
    ) -> List[DeliveryNote]:
        """
        Cerca DDT candidati per matching.
        Per default filtra solo per fornitore, opzionalmente per numero/data e stato.
        """
        query = (
            self.session.query(DeliveryNote)
            .options(
                joinedload(DeliveryNote.supplier),
                joinedload(DeliveryNote.legal_entity),
            )
            .filter(DeliveryNote.supplier_id == supplier_id)
        )
        if ddt_number:
            query = query.filter(DeliveryNote.ddt_number == ddt_number)
        if ddt_date:
            query = query.filter(DeliveryNote.ddt_date == ddt_date)
        if allowed_statuses:
            query = query.filter(DeliveryNote.status.in_(allowed_statuses))
        if exclude_document_ids:
            query = query.filter(~DeliveryNote.document_id.in_(exclude_document_ids))
        return (
            query.order_by(DeliveryNote.ddt_date.desc(), DeliveryNote.id.desc())
            .limit(limit)
            .all()
        )

    def list_by_document(self, document_id: int) -> List[DeliveryNote]:
        return (
            self.session.query(DeliveryNote)
            .filter(DeliveryNote.document_id == document_id)
            .order_by(DeliveryNote.ddt_date.desc(), DeliveryNote.id.desc())
            .all()
        )
