"""
Modello DocumentAuditLog (tabella: document_audit_logs).

Storico modifiche ed eliminazioni per i documenti.
"""
from datetime import datetime

from app.extensions import db


class DocumentAuditLog(db.Model):
    __tablename__ = "document_audit_logs"

    id = db.Column(db.BigInteger, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = db.Column(db.String(16), nullable=False, index=True)
    payload = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    document = db.relationship("Document", back_populates="audit_logs")

    def __repr__(self) -> str:
        return (
            f"<DocumentAuditLog id={self.id} document_id={self.document_id} "
            f"action={self.action!r}>"
        )
