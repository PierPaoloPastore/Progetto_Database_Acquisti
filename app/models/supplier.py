"""
Modello Supplier (tabella: suppliers).

Rappresenta un fornitore del ciclo di acquisti.
"""

from datetime import datetime

from app.extensions import db


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)

    # Dati anagrafici base
    name = db.Column(db.String(255), nullable=False, index=True)
    vat_number = db.Column(db.String(32), nullable=True, unique=True, index=True)  # Partita IVA
    fiscal_code = db.Column(db.String(32), nullable=True)  # Codice fiscale
    sdi_code = db.Column(db.String(16), nullable=True)  # Codice destinatario/SDI
    pec_email = db.Column(db.String(255), nullable=True)

    # Contatti / indirizzo
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(64), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    postal_code = db.Column(db.String(16), nullable=True)
    city = db.Column(db.String(128), nullable=True)
    province = db.Column(db.String(64), nullable=True)
    country = db.Column(db.String(64), nullable=True, default="IT")

    # Stato
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relazioni
    # Note: La relazione 'documents' è creata automaticamente da Document.supplier (backref)

    @property
    def invoices(self):
        """
        Backward compatibility: filtra i documents per tipo 'invoice'.
        Restituisce solo le fatture associate a questo fornitore.
        """
        return [doc for doc in self.documents if doc.document_type == 'invoice']

    def __repr__(self) -> str:
        return f"<Supplier id={self.id} name={self.name!r}>"
