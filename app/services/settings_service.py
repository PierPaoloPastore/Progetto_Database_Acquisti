"""
Servizi per la gestione delle impostazioni applicative.
"""

import os
from flask import current_app

def get_setting(key: str, default: str = "") -> str:
    return current_app.config.get(key, default)

def set_setting(key: str, value: str) -> None:
    current_app.config[key] = value

def _resolve_path(config_value: str | None, default_parts: list[str]) -> str:
    if config_value:
        target_path = os.path.abspath(config_value)
    else:
        base_dir = os.getcwd()
        target_path = os.path.join(base_dir, *default_parts)
    os.makedirs(target_path, exist_ok=True)
    return target_path

def _split_filename(filename: str) -> tuple[str, str]:
    lower_name = filename.lower()
    if lower_name.endswith(".xml.p7m"):
        suffix_len = len(".xml.p7m")
        return filename[:-suffix_len], filename[-suffix_len:]
    base, ext = os.path.splitext(filename)
    return base, ext

def ensure_unique_filename(base_dir: str, filename: str) -> str:
    base, ext = _split_filename(filename)
    candidate = filename
    counter = 1
    while os.path.exists(os.path.join(base_dir, candidate)):
        candidate = f"{base}_{counter}{ext}"
        counter += 1
    return candidate

def get_physical_copy_storage_path() -> str:
    """Restituisce il percorso assoluto per lo storage delle copie fisiche (Archivio)."""
    configured_path = current_app.config.get("PHYSICAL_COPY_STORAGE_PATH")
    
    return _resolve_path(configured_path, ["storage", "documenti"])

def get_scan_inbox_path() -> str:
    """Restituisce il percorso assoluto della Inbox (scansioni in arrivo)."""
    configured_path = current_app.config.get("SCAN_INBOX_PATH")
    
    return _resolve_path(configured_path, ["storage", "inbox", "documenti"])

def get_xml_inbox_path() -> str:
    """Restituisce il percorso assoluto della Inbox XML (import fatture)."""
    configured_path = current_app.config.get("XML_INBOX_PATH") or current_app.config.get("IMPORT_XML_FOLDER")
    return _resolve_path(configured_path, ["storage", "inbox", "xml"])

def get_payment_inbox_path() -> str:
    """Restituisce il percorso assoluto della Inbox pagamenti."""
    configured_path = current_app.config.get("PAYMENT_INBOX_PATH")
    return _resolve_path(configured_path, ["storage", "inbox", "pagamenti"])

def get_payment_files_storage_path() -> str:
    """Restituisce il percorso assoluto per lo storage dei PDF di pagamento."""
    configured_path = current_app.config.get("PAYMENT_FILES_STORAGE_PATH")
    
    return _resolve_path(configured_path, ["storage", "pagamenti"])


def get_delivery_note_storage_path() -> str:
    """Restituisce il percorso assoluto per lo storage dei PDF DDT."""
    configured_path = current_app.config.get("DELIVERY_NOTE_STORAGE_PATH")
    return _resolve_path(configured_path, ["storage", "ddt"])


def get_xml_storage_path() -> str:
    """Deposito interno per gli XML importati."""
    configured_path = current_app.config.get("XML_STORAGE_PATH")
    return _resolve_path(configured_path, ["storage", "xml"])


def get_documents_storage_path() -> str:
    """Deposito interno per i PDF dei documenti di acquisto."""
    return get_physical_copy_storage_path()


def get_xml_archive_path(year: int, base_path: str | None = None) -> str:
    base = os.path.abspath(base_path) if base_path else get_xml_inbox_path()
    target = os.path.join(base, "Archivio", "XML", str(year))
    os.makedirs(target, exist_ok=True)
    return target


def get_documents_archive_path(year: int, base_path: str | None = None) -> str:
    base = os.path.abspath(base_path) if base_path else get_scan_inbox_path()
    target = os.path.join(base, "Archivio", "Documenti", str(year))
    os.makedirs(target, exist_ok=True)
    return target


def get_payments_archive_path(year: int, base_path: str | None = None) -> str:
    base = os.path.abspath(base_path) if base_path else get_payment_inbox_path()
    target = os.path.join(base, "Archivio", "Pagamenti", str(year))
    os.makedirs(target, exist_ok=True)
    return target


def get_ddt_archive_path(year: int, base_path: str | None = None) -> str:
    base = os.path.abspath(base_path) if base_path else get_scan_inbox_path()
    target = os.path.join(base, "Archivio", "DDT", str(year))
    os.makedirs(target, exist_ok=True)
    return target


def get_attachments_storage_path() -> str:
    """Percorso assoluto per gli allegati FatturaPA."""
    configured_path = current_app.config.get("ATTACHMENTS_STORAGE_PATH")
    return _resolve_path(configured_path, ["storage", "attachments"])


def resolve_storage_path(base_path: str, relative_path: str) -> str:
    """
    Costruisce un percorso assoluto a partire dalla base storage e un path relativo salvato nel DB.
    """
    return os.path.abspath(os.path.join(base_path, relative_path))
