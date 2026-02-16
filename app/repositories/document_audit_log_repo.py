"""
Repository per il modello DocumentAuditLog.
"""
from typing import List, Optional

from app.models import DocumentAuditLog
from app.repositories.base import SqlAlchemyRepository


class DocumentAuditLogRepository(SqlAlchemyRepository[DocumentAuditLog]):
    def __init__(self, session):
        super().__init__(session, DocumentAuditLog)

    def list_recent(self, limit: int = 200) -> List[DocumentAuditLog]:
        return (
            self.session.query(DocumentAuditLog)
            .order_by(DocumentAuditLog.created_at.desc(), DocumentAuditLog.id.desc())
            .limit(limit)
            .all()
        )

    def list_by_document(self, document_id: int, limit: int = 100) -> List[DocumentAuditLog]:
        return (
            self.session.query(DocumentAuditLog)
            .filter(DocumentAuditLog.document_id == document_id)
            .order_by(DocumentAuditLog.created_at.desc(), DocumentAuditLog.id.desc())
            .limit(limit)
            .all()
        )
