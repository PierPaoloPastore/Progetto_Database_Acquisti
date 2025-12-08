"""Modello LegalEntity (tabella: legal_entities)."""

from datetime import datetime

from app.extensions import db


class LegalEntity(db.Model):
    __tablename__ = "legal_entities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    vat_number = db.Column(db.String, unique=True, nullable=False)
    fiscal_code = db.Column(db.String, nullable=True)
    address = db.Column(db.String, nullable=True)
    city = db.Column(db.String, nullable=True)
    country = db.Column(db.String, nullable=True, default="IT")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relazioni
    # Note: La relazione 'documents' è creata automaticamente da Document.legal_entity (backref)

    @property
    def invoices(self):
        """
        Backward compatibility: filtra i documents per tipo 'invoice'.
        Restituisce solo le fatture associate a questo intestatario.
        """
        return [doc for doc in self.documents if doc.document_type == 'invoice']

    def __repr__(self) -> str:
        return f"<LegalEntity id={self.id} name={self.name!r}>"

