import os
import shutil
from datetime import datetime
from pathlib import Path

from app.extensions import db
from app.models import Invoice
from app.services import get_setting


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
    invoice.physical_copy_file = dest_name
    invoice.physical_copy_status = "received"
    invoice.physical_copy_received_at = datetime.utcnow()

    # Se necessario, aggiorna stato documentale
    if invoice.doc_status == "imported":
        invoice.doc_status = "verified"

    db.session.commit()

    return dest_name
