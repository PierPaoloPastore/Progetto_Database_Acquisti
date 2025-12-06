"""
Modello DeliveryNote (tabella: delivery_notes).

DDT / Bolle di consegna.
Gestisce sia DDT attesi da XML (fatture differite) sia DDT reali importati da PDF.
"""

from datetime import datetime

from app.extensions import db


class DeliveryNote(db.Model):
    __tablename__ = "delivery_notes"

    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    supplier_id = db.Column(
        db.Integer,
        db.ForeignKey("suppliers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    legal_entity_id = db.Column(
        db.Integer,
        db.ForeignKey("legal_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Dati DDT
    ddt_number = db.Column(db.String(64), nullable=False, index=True)
    ddt_date = db.Column(db.Date, nullable=False, index=True)
    total_amount = db.Column(db.Numeric(15, 2), nullable=True)

    # File associato
    file_path = db.Column(db.String(255), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)

    # Provenienza
    # Valori: 'xml_expected', 'pdf_import', 'manual'
    source = db.Column(db.String(32), nullable=False, default="pdf_import", index=True)
    import_source = db.Column(db.String(255), nullable=True)
    imported_at = db.Column(db.DateTime, nullable=True)

    # Stato
    # Valori: 'unmatched', 'matched', 'missing', 'linked', 'ignored'
    status = db.Column(db.String(32), nullable=False, default="unmatched", index=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    document = db.relationship("Document", backref="delivery_notes")
    supplier = db.relationship("Supplier", backref="delivery_notes")
    legal_entity = db.relationship("LegalEntity", backref="delivery_notes")

    def __repr__(self) -> str:
        return (
            f"<DeliveryNote id={self.id} ddt_number={self.ddt_number!r} "
            f"ddt_date={self.ddt_date} status={self.status!r}>"
        )
