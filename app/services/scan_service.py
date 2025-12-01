import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Invoice
from app.services.settings_service import (
    get_physical_copy_storage_path,
    get_setting,
)


def list_inbox_files() -> list[str]:
    """
    Ritorna l'elenco dei file presenti nella cartella inbox
    configurata nelle impostazioni.
    """
    inbox_path = get_setting("SCAN_INBOX_PATH", "")
    if not inbox_path or not os.path.isdir(inbox_path):
        return []

    files = []
    for entry in os.listdir(inbox_path):
        full_path = os.path.join(inbox_path, entry)
        if os.path.isfile(full_path):
            files.append(entry)

    return sorted(files)


def attach_scan_to_invoice(filename: str, invoice: Invoice) -> str:
    """
    Sposta un file dalla inbox allo storage definitivo, aggiorna la fattura
    e ritorna il path relativo del file salvato.
    """
    inbox_path = get_setting("SCAN_INBOX_PATH", "")
    storage_path = get_setting("PHYSICAL_COPY_STORAGE_PATH", "")

    if not inbox_path or not storage_path:
        raise ValueError("Percorsi inbox/storage non configurati.")

    src = Path(inbox_path) / filename

    if not src.exists():
        raise FileNotFoundError(f"File {filename} non trovato nella inbox.")

    # Nome file normalizzato
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    cleaned_number = str(invoice.id)
    dest_name = f"invoice_{cleaned_number}_{timestamp}{src.suffix}"

    dest_dir = Path(storage_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / dest_name

    # Sposta il file (copy+delete o rename se stesso filesystem)
    shutil.move(str(src), str(dest))

    # Path relativo salvato in DB
    invoice.physical_copy_file_path = str(dest)
    invoice.physical_copy_status = "received"
    invoice.physical_copy_received_at = datetime.utcnow()

    # Se necessario, aggiorna stato documentale
    if invoice.doc_status == "imported":
        invoice.doc_status = "verified"

    db.session.commit()

    return dest_name


def _build_physical_copy_filename(invoice: Invoice, original_filename: str) -> str:
    name, ext = os.path.splitext(secure_filename(original_filename))
    ext = ext or ""
    cleaned_number = re.sub(r"[^A-Za-z0-9]+", "_", invoice.invoice_number or "")
    cleaned_date = ""
    if invoice.invoice_date:
        cleaned_date = re.sub(r"[^A-Za-z0-9]+", "_", invoice.invoice_date.isoformat())
    return f"fattura_{invoice.id}_{cleaned_number}_{cleaned_date}{ext}"


def store_physical_copy(invoice: Invoice, file: FileStorage) -> str:
    """Salva una copia fisica caricata e ritorna il percorso completo."""
    storage_path = Path(get_physical_copy_storage_path())
    storage_path.mkdir(parents=True, exist_ok=True)

    filename = _build_physical_copy_filename(invoice, file.filename or "file")
    destination = storage_path / filename
    file.save(destination)

    return str(destination)
