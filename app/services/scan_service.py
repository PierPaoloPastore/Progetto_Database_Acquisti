"""
Servizio per la gestione delle scansioni e dei file fisici.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Callable
from werkzeug.datastructures import FileStorage

from app.services import settings_service

def store_payment_document_file(file: FileStorage, base_path: str, filename: str) -> str:
    """Salva un file di pagamento."""
    return _store_file(file, base_path, filename, settings_service.get_payments_archive_path)


def store_delivery_note_file(file: FileStorage, base_path: str, filename: str) -> str:
    """Salva un PDF di DDT sotto la cartella base, organizzato per anno."""
    return _store_file(file, base_path, filename, settings_service.get_ddt_archive_path)


def _store_file(
    file: FileStorage, base_path: str, filename: str,
    get_archive_path: Callable[[int], str],
) -> str:
    now = datetime.now()
    year_str = str(now.year)
    dest_dir = os.path.join(base_path, year_str)
    os.makedirs(dest_dir, exist_ok=True)

    safe_name = settings_service.ensure_unique_filename(dest_dir, filename)
    dest_path = os.path.join(dest_dir, safe_name)
    file.save(dest_path)

    archive_dir = get_archive_path(now.year)
    archive_name = settings_service.ensure_unique_filename(archive_dir, safe_name)
    shutil.copy2(dest_path, os.path.join(archive_dir, archive_name))

    return os.path.join(year_str, safe_name)
