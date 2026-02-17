"""
Servizi di manutenzione e ripristino dati applicativi.
"""

from __future__ import annotations

import os
from pathlib import Path

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


def cleanup_physical_copies() -> dict:
    """
    Elimina i file delle copie fisiche dal deposito configurato.

    Ritorna un dict con il riepilogo dell'operazione.
    """
    from app.services.settings_service import get_setting

    configured_path = (get_setting("PHYSICAL_COPY_STORAGE_PATH", "") or "").strip()
    if configured_path:
        base_path = os.path.abspath(configured_path)
    else:
        base_path = os.path.join(os.getcwd(), "storage", "documenti")

    result = {
        "path": base_path,
        "removed_files": 0,
        "removed_dirs": 0,
        "skipped": False,
    }

    if not os.path.isdir(base_path):
        result["skipped"] = True
        return result

    resolved = Path(base_path).resolve()
    if resolved == Path(resolved.anchor):
        raise ValueError("Percorso deposito copie fisiche non valido.")

    for root, dirs, files in os.walk(base_path, topdown=False):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                os.remove(file_path)
                result["removed_files"] += 1
            except OSError:
                continue
        for dirname in dirs:
            dir_path = os.path.join(root, dirname)
            try:
                os.rmdir(dir_path)
                result["removed_dirs"] += 1
            except OSError:
                continue

    return result
