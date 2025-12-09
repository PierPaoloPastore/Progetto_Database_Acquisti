"""
Servizio per la gestione delle scansioni e dei file fisici.

Gestisce:
- salvataggio file caricati (upload)
- organizzazione cartelle per anno/mese
- collegamento file al DB
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from flask import current_app

# FIX: Sostituito Invoice con Document
from app.models import Document, PaymentDocument
from app.services import settings_service


def list_inbox_files() -> List[str]:
    """Elenca i file presenti nella cartella INBOX (scansioni da smistare)."""
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
    Salva il file della copia fisica per un documento specifico.
    Organizza i file in: /storage/scans/YYYY/MM/doc_ID_filename
    Restituisce il path relativo salvato nel DB.
    """
    base_path = settings_service.get_scan_storage_path()
    
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

    # Restituisce path relativo per portabilità
    return os.path.join(year_str, month_str, final_name)


def attach_scan_to_invoice(filename: str, document: Document) -> str:
    """
    Sposta un file dalla INBOX alla cartella di archiviazione del documento.
    Aggiorna il documento col nuovo path.
    """
    inbox_path = settings_service.get_scan_inbox_path()
    source_path = os.path.join(inbox_path, filename)

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"File {filename} non trovato nella inbox.")

    # Simula un FileStorage aprendo il file locale
    with open(source_path, "rb") as f:
        # Creiamo un oggetto compatibile o usiamo logica custom di spostamento
        # Qui usiamo la logica di 'store_physical_copy' ma adattata per file locale
        
        base_path = settings_service.get_scan_storage_path()
        ref_date = document.document_date or datetime.today().date()
        year_str = str(ref_date.year)
        month_str = f"{ref_date.month:02d}"

        dest_dir = os.path.join(base_path, year_str, month_str)
        os.makedirs(dest_dir, exist_ok=True)

        final_name = f"doc_{document.id}_{secure_filename(filename)}"
        dest_path = os.path.join(dest_dir, final_name)

        # Sposta fisicamente il file (move)
        shutil.move(source_path, dest_path)

        # Calcola relative path
        relative_path = os.path.join(year_str, month_str, final_name)

        # Aggiorna il DB
        from app.extensions import db
        document.physical_copy_file_path = relative_path
        document.physical_copy_status = "received"
        document.physical_copy_received_at = datetime.utcnow()
        if document.doc_status == "imported":
            document.doc_status = "verified"
        
        db.session.add(document)
        db.session.commit()

        return relative_path


def store_payment_document_file(
    file: FileStorage, base_path: str, filename: str
) -> str:
    """
    Salva un file di pagamento nella cartella specificata.
    Organizza per YYYY/MM corrente.
    """
    now = datetime.now()
    year_str = str(now.year)
    month_str = f"{now.month:02d}"

    dest_dir = os.path.join(base_path, year_str, month_str)
    os.makedirs(dest_dir, exist_ok=True)

    dest_path = os.path.join(dest_dir, filename)
    file.save(dest_path)

    return os.path.join(year_str, month_str, filename)