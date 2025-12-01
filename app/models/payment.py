"""
Modello Payment (tabella: payments).

Rappresenta una scadenza o un pagamento associato alla fattura,
derivato da DatiPagamento / DettaglioPagamento.
"""

from datetime import datetime

from app.extensions import db


class PaymentDocument(db.Model):
    __tablename__ = "payment_documents"

    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    payment_type = db.Column(db.String(32), nullable=False, default="sconosciuto")
    status = db.Column(db.String(32), nullable=False, default="pending_review", index=True)
    uploaded_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    parsed_amount = db.Column(db.Numeric(15, 2), nullable=True)
    parsed_payment_date = db.Column(db.Date, nullable=True)
    parsed_invoice_number = db.Column(db.String(100), nullable=True)
    parse_error_message = db.Column(db.Text, nullable=True)

    payments = db.relationship("Payment", back_populates="payment_document")

    def __repr__(self) -> str:
        return f"<PaymentDocument id={self.id} file_name={self.file_name!r} status={self.status!r}>"


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)

    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    payment_document_id = db.Column(
        db.Integer,
        db.ForeignKey("payment_documents.id"),
        nullable=True,
        index=True,
    )

    # Dati scadenza / pagamento previsti
    due_date = db.Column(db.Date, nullable=True, index=True)
    expected_amount = db.Column(db.Numeric(15, 2), nullable=True)
    payment_terms = db.Column(db.String(128), nullable=True)  # es. 30 gg f.m.
    payment_method = db.Column(db.String(64), nullable=True)  # es. bonifico, RID

    # Dati pagamento effettivo
    paid_date = db.Column(db.Date, nullable=True, index=True)
    paid_amount = db.Column(db.Numeric(15, 2), nullable=True)

    # Stato
    # es. "unpaid", "partial", "paid", "overdue"
    status = db.Column(db.String(32), nullable=False, default="unpaid", index=True)

    # Note eventuali
    notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    invoice = db.relationship("Invoice", back_populates="payments")
    payment_document = db.relationship(
        "PaymentDocument", back_populates="payments", foreign_keys=[payment_document_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} invoice_id={self.invoice_id} "
            f"status={self.status!r}>"
        )
