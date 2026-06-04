from datetime import datetime

from app.extensions import db


class CreditNoteAllocation(db.Model):
    __tablename__ = "credit_note_allocations"

    id = db.Column(db.Integer, primary_key=True)

    credit_note_document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    invoice_document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    allocated_amount = db.Column(db.Numeric(15, 2), nullable=False)
    allocated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    notes = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    credit_note_document = db.relationship(
        "Document",
        foreign_keys=[credit_note_document_id],
        back_populates="credit_note_allocations_issued",
    )
    invoice_document = db.relationship(
        "Document",
        foreign_keys=[invoice_document_id],
        back_populates="credit_note_allocations_received",
    )

    def __repr__(self) -> str:
        return (
            f"<CreditNoteAllocation id={self.id} credit_note_document_id={self.credit_note_document_id} "
            f"invoice_document_id={self.invoice_document_id} amount={self.allocated_amount}>"
        )
