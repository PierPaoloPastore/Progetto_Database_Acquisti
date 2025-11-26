#!/usr/bin/env python3
"""
Script di avvio per l'applicazione Flask gestionale acquisti.

Uso:
    python manage.py runserver  # Avvia il server di sviluppo
    python manage.py create-db  # Crea le tabelle del database MySQL
"""

import argparse
import logging
import os

from sqlalchemy.exc import OperationalError as SAOperationalError
from pymysql.err import OperationalError as MySQLOperationalError

from app import create_app
from app.extensions import db
from config import DevConfig

# Configurazione del logger per l'uso standalone (fuori dal contesto Flask)
cli_logger = logging.getLogger("manage_cli")
cli_logger.setLevel(logging.INFO)
cli_handler = logging.StreamHandler()
cli_handler.setFormatter(logging.Formatter("%(levelname)s: %(name)s: %(message)s"))
if not cli_logger.handlers:
    cli_logger.addHandler(cli_handler)


def _import_all_models() -> None:
    """Assicura che tutti i modelli siano registrati prima di create_all()."""
    # Import globale dei modelli: è sufficiente importare il pacchetto app.models
    # per registrare tutte le classi con SQLAlchemy.
    import app.models  # noqa: F401


def create_db(app):
    """Crea tutte le tabelle del database definite nei modelli SQLAlchemy."""
    with app.app_context():
        cli_logger.info("Tentativo di creare tutte le tabelle nel database...")
        try:
            _import_all_models()
            db.create_all()
            cli_logger.info("Database creato con successo.")
        except (SAOperationalError, MySQLOperationalError) as e:
            cli_logger.error(
                "Errore di connessione o permessi MySQL: %s",
                e,
            )
            cli_logger.info(
                "Verifica che MySQL sia attivo e che l'utente '%s' abbia accesso al DB '%s'.",
                app.config.get("DB_USER"),
                app.config.get("DB_NAME"),
            )
        except Exception as e:  # noqa: BLE001
            cli_logger.error(f"Errore durante la creazione del database: {e}")
            cli_logger.info(
                "Se l'errore non è di permessi/connessione MySQL, controlla i modelli o le migrazioni."
            )


def run_server(app):
    """Avvia il server di sviluppo Flask."""
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))

    app.logger.info(f"Avvio del server su http://{host}:{port}")
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))


def main() -> None:
    """Punto di ingresso principale per gestire i comandi CLI."""
    parser = argparse.ArgumentParser(
        description="Gestione dell'applicazione Flask gestionale acquisti."
    )
    parser.add_argument(
        "command",
        choices=["runserver", "create-db"],
        help="Il comando da eseguire.",
    )

    args = parser.parse_args()

    # Crea l'app con la configurazione di sviluppo
    app = create_app(DevConfig)

    if args.command == "runserver":
        run_server(app)
    elif args.command == "create-db":
        create_db(app)


if __name__ == "__main__":
    main()
