"""
Modello Invoice (tabella: invoices).

Rappresenta una fattura di acquisto, una per file XML importato.
"""

from datetime import datetime

from app.extensions import db


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)

    # Collegamento al fornitore
    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Identificazione documento
    invoice_number = db.Column(db.String(64), nullable=False, index=True)
    invoice_series = db.Column(db.String(32), nullable=True)
    invoice_date = db.Column(db.Date, nullable=False, index=True)
    registration_date = db.Column(db.Date, nullable=True, index=True)

    # Importi principali
    total_taxable_amount = db.Column(db.Numeric(15, 2), nullable=True)
    total_vat_amount = db.Column(db.Numeric(15, 2), nullable=True)
    total_gross_amount = db.Column(db.Numeric(15, 2), nullable=True)
    currency = db.Column(db.String(8), nullable=False, default="EUR")

    # Stato documento / pagamento
    # status_documento es: "imported", "verified", "archived"
    doc_status = db.Column(db.String(32), nullable=False, default="imported", index=True)
    # stato_pagamento es: "unpaid", "partial", "paid"
    payment_status = db.Column(
        db.String(32), nullable=False, default="unpaid", index=True
    )

    # Scadenza principale (può essere derivata dai DatiPagamento)
    due_date = db.Column(db.Date, nullable=True, index=True)

    # Informazioni sul file sorgente (XML)
    file_name = db.Column(db.String(255), nullable=False, unique=True)
    file_hash = db.Column(db.String(128), nullable=True, unique=True)
    import_source = db.Column(db.String(255), nullable=True)  # es. cartella, batch
    imported_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    # Altri metadati
    notes_internal = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relazioni
    supplier = db.relationship("Supplier", back_populates="invoices")

    lines = db.relationship(
        "InvoiceLine",
        back_populates="invoice",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    vat_summaries = db.relationship(
        "VatSummary",
        back_populates="invoice",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    payments = db.relationship(
        "Payment",
        back_populates="invoice",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    notes = db.relationship(
        "Note",
        back_populates="invoice",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Invoice id={self.id} number={self.invoice_number!r} "
            f"supplier_id={self.supplier_id}>"
        )
