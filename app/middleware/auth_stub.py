"""
Middleware di autenticazione fittizia (stub).

Obiettivo:
- Fornire un oggetto `current_user` fittizio per tutte le richieste,
  accessibile tramite `flask.g.current_user` e nei template Jinja come `current_user`.
- NON bloccare nessuna route: non ci sono redirect, 401 o controlli reali.

In futuro:
- Questo modulo potrà essere sostituito o esteso con un vero sistema di autenticazione
  (es. Flask-Login, JWT, integrazione con SSO aziendale, ecc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from flask import g, request, Flask


@dataclass
class CurrentUserStub:
    """
    Rappresenta un utente fittizio.

    Campi minimi:
    - id: identificativo interno (fittizio)
    - username: nome utente
    - full_name: nome completo
    - is_admin: flag per eventuali controlli futuri nei template
    """

    id: int
    username: str
    full_name: str
    is_admin: bool = False


def init_auth_stub(app: Flask) -> None:
    """
    Registra gli hook di autenticazione fittizia sull'app Flask.

    - before_request: imposta g.current_user
    - context_processor: espone current_user ai template Jinja
    """

    @app.before_request
    def inject_current_user_stub() -> None:
        """
        Esegue prima di ogni richiesta.

        In un sistema reale qui verrebbe:
        - letto un cookie di sessione
        - validato un token JWT
        - recuperato l'utente dal DB
        ecc.

        In questa versione:
        - assegniamo sempre lo stesso utente fittizio.
        """
        # Puoi usare request.remote_addr solo per logging in futuro, qui è un placeholder
        _ = request.remote_addr

        # Utente fittizio costante
        g.current_user = CurrentUserStub(
            id=1,
            username="admin",
            full_name="Utente Demo",
            is_admin=True,
        )

    @app.context_processor
    def inject_user_into_templates():
        """
        Rende `current_user` disponibile in tutti i template Jinja2.

        Esempio in un template:
            {% if current_user %}
                Benvenuto, {{ current_user.full_name }}
            {% endif %}
        """
        user: Optional[CurrentUserStub] = getattr(g, "current_user", None)
        return {"current_user": user}
