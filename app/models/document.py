"""
Modello Document (tabella: documents).

Single Table Inheritance per tutti i documenti economici:
fatture, F24, assicurazioni, MAV, CBILL, scontrini, affitti, tributi.
"""

from datetime import datetime
from typing import Optional

from app.extensions import db

class Document(db.Model):
    """
    Supertipo per tutti i documenti economici.
    Utilizza Single Table Inheritance con discriminatore document_type.
    """

    __tablename__ = "documents"

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Discriminatore per Single Table Inheritance
    document_type = db.Column(db.String(32), nullable=False, index=True)

    # Foreign keys comuni
    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    legal_entity_id = db.Column(
        db.Integer,
        db.ForeignKey("legal_entities.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # Identificazione documento (colonne comuni)
    document_number = db.Column(db.String(64), nullable=True, index=True)
    document_date = db.Column(db.Date, nullable=True, index=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    registration_date = db.Column(db.Date, nullable=True, index=True)

    # Importi principali (colonne comuni)
    total_taxable_amount = db.Column(db.Numeric(15, 2), nullable=True)
    total_vat_amount = db.Column(db.Numeric(15, 2), nullable=True)
    total_gross_amount = db.Column(db.Numeric(15, 2), nullable=True)

    # Stato documento (colonne comuni)
    doc_status = db.Column(db.String(32), nullable=False, default="imported", index=True)

    # --- CAMPO NUOVO (per gestione pagamenti) ---
    is_paid = db.Column(db.Boolean, nullable=False, default=False, index=True)
    # --------------------------------------------

    # Informazioni sul file sorgente
    import_source = db.Column(db.String(255), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=True) 
    imported_at = db.Column(db.DateTime, nullable=True, index=True)

    # Path relativo per la copia fisica scansionata/caricata
    physical_copy_file_path = db.Column(db.String(500), nullable=True)

    # Stato copia fisica
    physical_copy_status = db.Column(
        db.String(32), nullable=False, default="missing", index=True
    )
    physical_copy_requested_at = db.Column(db.DateTime, nullable=True)
    physical_copy_received_at = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Colonne specifiche INVOICE
    invoice_type = db.Column(db.String(32), nullable=True)

    # Colonne specifiche F24
    f24_period_from = db.Column(db.Date, nullable=True)
    f24_period_to = db.Column(db.Date, nullable=True)
    f24_tax_type = db.Column(db.String(64), nullable=True)
    f24_payment_code = db.Column(db.String(64), nullable=True)

    # Colonne specifiche INSURANCE
    insurance_policy_number = db.Column(db.String(64), nullable=True)
    insurance_coverage_start = db.Column(db.Date, nullable=True)
    insurance_coverage_end = db.Column(db.Date, nullable=True)
    insurance_type = db.Column(db.String(64), nullable=True)
    insurance_asset_description = db.Column(db.Text, nullable=True)

    # Colonne specifiche RENT
    rent_contract_id = db.Column(
        db.Integer,
        db.ForeignKey("rent_contracts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rent_period_month = db.Column(db.Integer, nullable=True)
    rent_period_year = db.Column(db.Integer, nullable=True)
    rent_property_description = db.Column(db.Text, nullable=True)

    # Colonne specifiche MAV/CBILL
    payment_code = db.Column(db.String(64), nullable=True)
    creditor_entity = db.Column(db.String(255), nullable=True)

    # Colonne specifiche RECEIPT
    receipt_merchant = db.Column(db.String(255), nullable=True)
    receipt_category = db.Column(db.String(64), nullable=True)

    # Colonne specifiche TAX
    tax_type = db.Column(db.String(64), nullable=True)
    tax_period_year = db.Column(db.Integer, nullable=True)
    tax_period_description = db.Column(db.String(255), nullable=True)

    # Relationships
    supplier = db.relationship("Supplier", backref="documents")
    legal_entity = db.relationship("LegalEntity", backref="documents")

    invoice_lines = db.relationship(
        "DocumentLine",
        back_populates="document",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="DocumentLine.document_id",
    )

    vat_summaries = db.relationship(
        "VatSummary",
        back_populates="document",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="VatSummary.document_id",
    )

    payments = db.relationship(
        "Payment",
        back_populates="document",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="Payment.document_id",
    )

    delivery_notes = db.relationship(
        "DeliveryNote",
        back_populates="document",
        lazy="dynamic",
        foreign_keys="DeliveryNote.document_id",
    )

    notes = db.relationship(
        "Note",
        back_populates="document",
        lazy="dynamic",
        cascade="all, delete-orphan",
        foreign_keys="Note.document_id",
    )

    import_logs = db.relationship(
        "ImportLog",
        back_populates="document",
        lazy="dynamic",
        foreign_keys="ImportLog.document_id",
    )

    rent_contract = db.relationship(
        "RentContract",
        backref="documents",
        foreign_keys=[rent_contract_id],
    )

    @property
    def lines(self):
        """Alias di compatibilità per accedere alle righe fattura."""
        return self.invoice_lines

    # Helper properties per identificare il tipo di documento
    @property
    def is_invoice(self) -> bool:
        return self.document_type == "invoice"

    @property
    def is_f24(self) -> bool:
        return self.document_type == "f24"

    @property
    def is_insurance(self) -> bool:
        return self.document_type == "insurance"

    @property
    def is_mav(self) -> bool:
        return self.document_type == "mav"

    @property
    def is_cbill(self) -> bool:
        return self.document_type == "cbill"

    @property
    def is_receipt(self) -> bool:
        return self.document_type == "receipt"

    @property
    def is_rent(self) -> bool:
        return self.document_type == "rent"

    @property
    def is_tax(self) -> bool:
        return self.document_type == "tax"

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} type={self.document_type!r} "
            f"number={self.document_number!r}>"
        )