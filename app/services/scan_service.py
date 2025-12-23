"""
Servizio per la gestione delle scansioni e dei file fisici.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List

from werkzeug.datastructures import FileStorage

from app.services import settings_service

def list_inbox_files() -> List[str]:
    """Elenca i file presenti nella cartella INBOX."""
    inbox_path = settings_service.get_scan_inbox_path()
    if not os.path.exists(inbox_path):
        return []

    files = []
    for f in os.listdir(inbox_path):
        full_path = os.path.join(inbox_path, f)
        if os.path.isfile(full_path) and not f.startswith("."):
            files.append(f)
    return sorted(files)


def store_payment_document_file(file: FileStorage, base_path: str, filename: str) -> str:
    """Salva un file di pagamento."""
    now = datetime.now()
    year_str = str(now.year)
    month_str = f"{now.month:02d}"

    dest_dir = os.path.join(base_path, year_str, month_str)
    os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, filename)
    file.save(dest_path)

    return os.path.join(year_str, month_str, filename)


def store_delivery_note_file(file: FileStorage, base_path: str, filename: str) -> str:
    """Salva un PDF di DDT sotto la cartella base, organizzato per anno/mese."""
    now = datetime.now()
    year_str = str(now.year)
    month_str = f"{now.month:02d}"

    dest_dir = os.path.join(base_path, year_str, month_str)
    os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, filename)
    file.save(dest_path)

    return os.path.join(year_str, month_str, filename)
