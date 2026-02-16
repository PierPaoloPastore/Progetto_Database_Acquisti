"""
Modello BankAccount (tabella: bank_accounts).

Rappresenta un conto bancario associato a una intestazione.
"""

from datetime import datetime

from app.extensions import db


class BankAccount(db.Model):
    __tablename__ = "bank_accounts"

    iban = db.Column(db.String(34), primary_key=True)
    legal_entity_id = db.Column(
        db.Integer,
        db.ForeignKey("legal_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(128), nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    legal_entity = db.relationship("LegalEntity", backref="bank_accounts")

    def __repr__(self) -> str:
        return f"<BankAccount iban={self.iban!r} legal_entity_id={self.legal_entity_id}>"
