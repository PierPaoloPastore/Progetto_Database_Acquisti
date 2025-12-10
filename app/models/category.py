"""
Modello Category (tabella: categories).

Rappresenta una categoria gestionale da assegnare alle righe fattura
(es. 'sementi', 'concimi', 'manutenzioni', 'servizi', ecc.).
"""

from datetime import datetime

from app.extensions import db


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(128), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=True)

    # Può essere usata per "spegnere" categorie non più usate senza cancellare i dati
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relazioni
    invoice_lines = db.relationship(
        "DocumentLine",
        back_populates="category",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Category id={self.id} name={self.name!r}>"
