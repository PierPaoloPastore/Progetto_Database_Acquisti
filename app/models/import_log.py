"""
Modello ImportLog (tabella: import_logs).

Traccia i tentativi di import dei file XML:
- successo o errore
- messaggio di dettaglio
- eventuale collegamento alla fattura creata
"""

from datetime import datetime

from app.extensions import db


class ImportLog(db.Model):
    __tablename__ = "import_logs"

    id = db.Column(db.Integer, primary_key=True)

    file_name = db.Column(db.String(255), nullable=False, index=True)
    file_hash = db.Column(db.String(128), nullable=True, index=True)
    import_source = db.Column(db.String(255), nullable=True)  # es. cartella, batch id

    # Risultato dell'import
    status = db.Column(
        db.String(32),
        nullable=False,
        default="success",
        index=True,
    )  # es. "success", "error", "skipped"

    message = db.Column(db.Text, nullable=True)  # log sintetico/errore umano leggibile

    # Collegamento (opzionale) alla fattura creata
    invoice_id = db.Column(
        db.Integer,
        db.ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    invoice = db.relationship("Invoice", lazy="joined")

    def __repr__(self) -> str:
        return (
            f"<ImportLog id={self.id} file_name={self.file_name!r} "
            f"status={self.status!r}>"
        )
