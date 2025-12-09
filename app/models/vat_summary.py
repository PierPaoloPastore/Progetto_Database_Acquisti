"""
Modello VatSummary (tabella: vat_summaries).

Rappresenta i blocchi DatiRiepilogo dell'XML:
un record per ogni aliquota IVA presente in fattura.
"""

from datetime import datetime

from app.extensions import db


class VatSummary(db.Model):
    __tablename__ = "vat_summaries"

    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    vat_rate = db.Column(db.Numeric(5, 2), nullable=False)  # Aliquota IVA in percentuale
    taxable_amount = db.Column(db.Numeric(15, 2), nullable=False)  # Imponibile
    vat_amount = db.Column(db.Numeric(15, 2), nullable=False)  # Imposta
    vat_nature = db.Column(
        db.String(8), nullable=True
    )  # Natura operazione (es. N1, N2, N3...) se presente

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    document = db.relationship("Document", back_populates="vat_summaries")

    def __repr__(self) -> str:
        return (
            f"<VatSummary id={self.id} document_id={self.document_id} "
            f"vat_rate={self.vat_rate}>"
        )
