"""
Servizi per la gestione delle impostazioni applicative.

Al momento i valori vengono letti e scritti dalla configurazione
Flask in memoria.
"""

import os

from flask import current_app


def get_setting(key: str, default: str = "") -> str:
    """
    Recupera un'impostazione dalla configurazione dell'applicazione.

    :param key: nome della chiave di configurazione
    :param default: valore di fallback se la chiave non è presente
    :return: valore della configurazione come stringa
    """
    return current_app.config.get(key, default)


def set_setting(key: str, value: str) -> None:
    """
    Aggiorna o imposta un valore di configurazione.

    :param key: nome della chiave di configurazione
    :param value: valore da salvare
    """
    current_app.config[key] = value


def get_physical_copy_storage_path() -> str:
    """Restituisce il percorso assoluto per lo storage delle copie fisiche."""
    configured_path = current_app.config.get("PHYSICAL_COPY_STORAGE_PATH")
    if configured_path:
        return os.path.abspath(configured_path)

    inbox_base = current_app.config.get("SCAN_INBOX_PATH", "")
    default_base = inbox_base if inbox_base else os.getcwd()
    default_path = os.path.join(default_base, "copies")
    return os.path.abspath(default_path)


def get_payment_files_storage_path() -> str:
    """Restituisce il percorso assoluto per lo storage dei PDF di pagamento."""

    configured_path = current_app.config.get("PAYMENT_FILES_STORAGE_PATH")
    if configured_path:
        target_path = os.path.abspath(configured_path)
    else:
        inbox_base = current_app.config.get("SCAN_INBOX_PATH", "")
        default_base = inbox_base if inbox_base else os.getcwd()
        target_path = os.path.abspath(os.path.join(default_base, "payments"))

    os.makedirs(target_path, exist_ok=True)
    return target_path
