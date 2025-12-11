"""
Servizio per la gestione delle scansioni e dei file fisici.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import List

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.models import Document
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

def store_physical_copy(document: Document, file: FileStorage) -> str:
    """
    Salva il file della copia fisica (upload diretto).
    """
    # FIX: Usa il nome corretto della funzione in settings_service
    base_path = settings_service.get_physical_copy_storage_path()
    
    # Usa la data del documento o oggi se mancante
    ref_date = document.document_date or datetime.today().date()
    year_str = str(ref_date.year)
    month_str = f"{ref_date.month:02d}"

    dest_dir = os.path.join(base_path, year_str, month_str)
    os.makedirs(dest_dir, exist_ok=True)

    filename = secure_filename(file.filename)
    # Prefisso con ID documento per univocità
    final_name = f"doc_{document.id}_{filename}"
    dest_path = os.path.join(dest_dir, final_name)

    file.save(dest_path)

    # Restituisce path relativo per portabilità (es: 2024/12/doc_1_file.pdf)
    return os.path.join(year_str, month_str, final_name)

def attach_scan_to_invoice(filename: str, document: Document) -> str:
    """
    Sposta un file dalla INBOX alla cartella di archiviazione (metodo legacy).
    """
    inbox_path = settings_service.get_scan_inbox_path()
    source_path = os.path.join(inbox_path, filename)

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"File {filename} non trovato nella inbox.")

    # FIX: Usa il nome corretto
    base_path = settings_service.get_physical_copy_storage_path()
    ref_date = document.document_date or datetime.today().date()
    year_str = str(ref_date.year)
    month_str = f"{ref_date.month:02d}"

    dest_dir = os.path.join(base_path, year_str, month_str)
    os.makedirs(dest_dir, exist_ok=True)

    final_name = f"doc_{document.id}_{secure_filename(filename)}"
    dest_path = os.path.join(dest_dir, final_name)

    # Sposta fisicamente il file
    shutil.move(source_path, dest_path)

    # Restituisce path relativo
    return os.path.join(year_str, month_str, final_name)

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