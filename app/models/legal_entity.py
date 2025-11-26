"""Modello SQLAlchemy per l'intestatario delle fatture."""

from datetime import datetime

from app.extensions import db


class LegalEntity(db.Model):
    __tablename__ = "legal_entities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    vat_number = db.Column(db.String(32), nullable=False, unique=True)
    fiscal_code = db.Column(db.String(32))
    address = db.Column(db.String(255))
    city = db.Column(db.String(128))
    country = db.Column(db.String(8), default="IT")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship("Invoice", back_populates="legal_entity", lazy="dynamic")

    def __repr__(self) -> str:  # pragma: no cover - rappresentazione debug
        return f"<LegalEntity id={self.id} name={self.name!r}>"
