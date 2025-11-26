#!/usr/bin/env python3
"""
Script di avvio per l'applicazione Flask gestionale acquisti.

Uso:
    python manage.py runserver  # Avvia il server di sviluppo
    python manage.py create-db  # Crea le tabelle del database MySQL
"""

import os
import argparse
import logging

from app import create_app
from app.extensions import db
from config import DevConfig

# Per l'inizializzazione del database è necessario importare tutti i modelli
# Anche se non usati direttamente, Flask-SQLAlchemy/SQLAlchemy ha bisogno di
# registrarli.
from app.models.supplier import Supplier  # Esempio: import del modello
# TODO: Assicurati di importare QUI tutti gli altri modelli che hai creato
# Esempio:
# from app.models.invoice import Invoice
# from app.models.vat_summary import VatSummary

# Configurazione del logger per l'uso standalone (fuori dal contesto Flask)
cli_logger = logging.getLogger("manage_cli")
cli_logger.setLevel(logging.INFO)
cli_handler = logging.StreamHandler()
cli_handler.setFormatter(logging.Formatter('%(levelname)s: %(name)s: %(message)s'))
cli_logger.addHandler(cli_handler)


def create_db(app):
    """Crea tutte le tabelle del database definite nei modelli SQLAlchemy."""
    with app.app_context():
        cli_logger.info("Tentativo di creare tutte le tabelle nel database...")
        try:
            # db.create_all() usa i metadati raccolti da tutti i modelli importati
            db.create_all()
            cli_logger.info("Database creato con successo.")
        except Exception as e:
            cli_logger.error(f"Errore durante la creazione del database: {e}")
            cli_logger.info("Verifica che il servizio MySQL sia attivo e che l'utente DB abbia i permessi corretti.")


def run_server(app):
    """Avvia il server di sviluppo Flask."""
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))
    
    app.logger.info(f"Avvio del server su http://{host}:{port}")
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))


def main() -> None:
    """Punto di ingresso principale per gestire i comandi CLI."""
    parser = argparse.ArgumentParser(description="Gestione dell'applicazione Flask gestionale acquisti.")
    parser.add_argument("command", choices=["runserver", "create-db"], help="Il comando da eseguire.")
    
    args = parser.parse_args()
    
    # Crea l'app con la configurazione di sviluppo
    app = create_app(DevConfig)

    if args.command == "runserver":
        run_server(app)
    elif args.command == "create-db":
        create_db(app)


if __name__ == "__main__":
    # Assicurati di avere tutti i modelli importati prima di main()
    # altrimenti create_db non saprà quali tabelle creare.
    # Ho aggiunto un import di esempio (Supplier) sopra.
    main()