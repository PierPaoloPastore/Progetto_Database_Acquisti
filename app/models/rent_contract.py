"""
Modello RentContract (tabella: rent_contracts).

Rappresenta un contratto di affitto collegato a documenti di tipo 'rent'.
Permette di gestire affitti periodici con importo mensile fisso.
"""

from datetime import datetime
from typing import Optional

from app.extensions import db


class RentContract(db.Model):
    """
    Contratto di affitto.

    Collega documenti di tipo 'rent' a un contratto sottostante,
    permettendo di tracciare pagamenti mensili ricorrenti.
    """

    __tablename__ = "rent_contracts"

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Identificazione contratto
    contract_number = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # Foreign keys
    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    legal_entity_id = db.Column(
        db.Integer,
        db.ForeignKey("legal_entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Dati immobile
    property_description = db.Column(db.Text, nullable=True)
    property_address = db.Column(db.String(255), nullable=True)

    # Dati economici
    monthly_amount = db.Column(db.Numeric(15, 2), nullable=False)

    # Date contratto
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=True, index=True)

    # Giorno di pagamento (1-31)
    payment_day = db.Column(db.Integer, nullable=False, default=1)

    # Stato
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)

    # Note
    notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    supplier = db.relationship("Supplier", backref="rent_contracts")
    legal_entity = db.relationship("LegalEntity", backref="rent_contracts")

    # Nota: la relationship verso Document è già definita in Document.rent_contract
    # con backref="documents", quindi non va ridefinita qui per evitare conflitti.
    # L'attributo `documents` è già disponibile tramite il backref.

    def __repr__(self) -> str:
        return (
            f"<RentContract id={self.id} number={self.contract_number!r} "
            f"is_active={self.is_active}>"
        )
