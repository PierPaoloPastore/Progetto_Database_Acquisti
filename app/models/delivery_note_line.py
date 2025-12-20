"""
Modello DeliveryNoteLine (righe DDT).
"""
from datetime import datetime

from app.extensions import db


class DeliveryNoteLine(db.Model):
    __tablename__ = "delivery_note_lines"

    id = db.Column(db.Integer, primary_key=True)

    delivery_note_id = db.Column(
        db.Integer,
        db.ForeignKey("delivery_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    line_number = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    item_code = db.Column(db.String(64), nullable=True, index=True)
    quantity = db.Column(db.Numeric(15, 4), nullable=True)
    uom = db.Column(db.String(16), nullable=True)
    amount = db.Column(db.Numeric(15, 2), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    delivery_note = db.relationship(
        "DeliveryNote", back_populates="delivery_note_lines"
    )

    def __repr__(self) -> str:
        return (
            f"<DeliveryNoteLine id={self.id} delivery_note_id={self.delivery_note_id} "
            f"line_number={self.line_number}>"
        )
