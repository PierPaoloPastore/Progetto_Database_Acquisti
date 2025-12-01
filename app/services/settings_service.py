"""
Servizi per la gestione delle impostazioni applicative.

Al momento i valori vengono letti e scritti dalla configurazione
Flask in memoria.
"""

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
    current_app.config[key] = value main
