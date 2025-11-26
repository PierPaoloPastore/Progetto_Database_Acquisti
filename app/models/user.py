"""
Modello User (tabella: users).

Rappresenta un utente del sistema.
Per ora è minimale: l'autenticazione reale verrà aggiunta in futuro.

Verrà usato anche dall'auth_stub middleware e per tracciare le note.
"""

from datetime import datetime

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(128), nullable=True)
    email = db.Column(db.String(255), nullable=True, unique=True)

    # Ruolo/logica di permessi (in futuro potrà essere gestita meglio)
    # es. "admin", "user", "readonly"
    role = db.Column(db.String(32), nullable=False, default="user")

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # Timestamps
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relazioni
    notes = db.relationship(
        "Note",
        back_populates="user",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
