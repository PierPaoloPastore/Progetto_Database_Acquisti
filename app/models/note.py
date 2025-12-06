"""
Modello Note (tabella: notes).

Consente di aggiungere note interne alle fatture (commenti, spiegazioni, ecc.).
"""

from datetime import datetime

from app.extensions import db


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # In futuro si potrà collegare a un utente specifico
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    content = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )

    document = db.relationship("Document", back_populates="notes")
    user = db.relationship("User", back_populates="notes", lazy="joined")

    def __repr__(self) -> str:
        return f"<Note id={self.id} document_id={self.document_id}>"
