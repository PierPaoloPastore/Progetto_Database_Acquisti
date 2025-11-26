"""
Modello LegalEntity (tabella: legal_entities).

Rappresenta l'intestatario delle fatture (azienda o professionista) a cui
sono associate le registrazioni contabili.
"""

from datetime import datetime

from app.extensions import db


class LegalEntity(db.Model):
    __tablename__ = "legal_entities"

    id = db.Column(db.Integer, primary_key=True)

    # Dati anagrafici base
    name = db.Column(db.String(255), nullable=False, index=True)
    vat_number = db.Column(db.String(32), nullable=True, index=True)
    tax_code = db.Column(db.String(32), nullable=True)

    # Stato
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relazioni
    invoices = db.relationship(
        "Invoice",
        back_populates="legal_entity",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<LegalEntity id={self.id} name={self.name!r}>"

