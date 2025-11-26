"""
Modello InvoiceLine (tabella: invoice_lines).

Rappresenta una singola riga della fattura (DettaglioLinee).
"""

from datetime import datetime

from app.extensions import db


class InvoiceLine(db.Model):
    __tablename__ = "invoice_lines"

    id = db.Column(db.Integer, primary_key=True)

    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Collegamento a categoria gestionale (es. 'sementi', 'concimi', 'servizi', ecc.)
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    line_number = db.Column(db.Integer, nullable=True)  # Numero riga da DettaglioLinee
    description = db.Column(db.Text, nullable=False)

    quantity = db.Column(db.Numeric(15, 4), nullable=True)
    unit_of_measure = db.Column(db.String(32), nullable=True)
    unit_price = db.Column(db.Numeric(15, 4), nullable=True)
    discount_amount = db.Column(db.Numeric(15, 2), nullable=True)
    discount_percent = db.Column(db.Numeric(7, 4), nullable=True)

    # Importi per riga
    taxable_amount = db.Column(db.Numeric(15, 2), nullable=True)
    vat_rate = db.Column(db.Numeric(5, 2), nullable=True)
    vat_amount = db.Column(db.Numeric(15, 2), nullable=True)
    total_line_amount = db.Column(db.Numeric(15, 2), nullable=True)

    # Eventuali riferimenti aggiuntivi (es. codici articolo, commessa, ecc.)
    sku_code = db.Column(db.String(64), nullable=True)
    internal_code = db.Column(db.String(64), nullable=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relazioni
    invoice = db.relationship("Invoice", back_populates="lines")
    category = db.relationship("Category", back_populates="invoice_lines")

    def __repr__(self) -> str:
        return f"<InvoiceLine id={self.id} invoice_id={self.invoice_id}>"
