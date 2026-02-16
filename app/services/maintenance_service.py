"""
Servizi di manutenzione e ripristino dati applicativi.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import text

from app.extensions import db


def initialize_database(*, preserve_settings: bool = True, preserve_users: bool = True) -> int:
    """
    Inizializza il database cancellando i dati applicativi.

    - preserve_settings: mantiene la tabella app_settings
    - preserve_users: mantiene la tabella users
    Ritorna il numero di tabelle ripulite.
    """
    # Assicuriamo che i modelli siano registrati nella metadata
    import app.models  # noqa: F401

    skip_tables = set()
    if preserve_settings:
        skip_tables.add("app_settings")
    if preserve_users:
        skip_tables.add("users")

    tables: list[str] = [
        table.name
        for table in db.metadata.sorted_tables
        if table.name not in skip_tables
    ]

    if not tables:
        return 0

    with db.engine.connect() as conn:
        try:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            for table_name in tables:
                conn.execute(text(f"TRUNCATE TABLE `{table_name}`"))
        finally:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        conn.commit()

    db.session.remove()
    return len(tables)
