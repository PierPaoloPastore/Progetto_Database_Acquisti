"""
Servizi per la gestione delle impostazioni applicative.
"""

import os
from flask import current_app

def get_setting(key: str, default: str = "") -> str:
    return current_app.config.get(key, default)

def set_setting(key: str, value: str) -> None:
    current_app.config[key] = value

def get_physical_copy_storage_path() -> str:
    """Restituisce il percorso assoluto per lo storage delle copie fisiche (Archivio)."""
    configured_path = current_app.config.get("PHYSICAL_COPY_STORAGE_PATH")
    
    if configured_path:
        target_path = os.path.abspath(configured_path)
    else:
        # Default: cartella 'storage/scans' nella root del progetto
        base_dir = os.getcwd()
        target_path = os.path.join(base_dir, "storage", "scans")

    os.makedirs(target_path, exist_ok=True)
    return target_path

def get_scan_inbox_path() -> str:
    """Restituisce il percorso assoluto della Inbox (scansioni in arrivo)."""
    configured_path = current_app.config.get("SCAN_INBOX_PATH")
    
    if configured_path:
        target_path = os.path.abspath(configured_path)
    else:
        # Default: cartella 'inbox' nella root del progetto
        base_dir = os.getcwd()
        target_path = os.path.join(base_dir, "inbox")
        
    os.makedirs(target_path, exist_ok=True)
    return target_path

def get_payment_files_storage_path() -> str:
    """Restituisce il percorso assoluto per lo storage dei PDF di pagamento."""
    configured_path = current_app.config.get("PAYMENT_FILES_STORAGE_PATH")
    
    if configured_path:
        target_path = os.path.abspath(configured_path)
    else:
        base_dir = os.getcwd()
        target_path = os.path.join(base_dir, "storage", "payments")

    os.makedirs(target_path, exist_ok=True)
    return target_path