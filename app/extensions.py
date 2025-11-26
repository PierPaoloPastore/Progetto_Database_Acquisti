"""
Modulo che contiene le estensioni Flask condivise (es. db, logger, ecc.).
"""

import json
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Istanza globale di SQLAlchemy, sarà inizializzata in create_app()
db = SQLAlchemy()


class JsonFormatter(logging.Formatter):
    """
    Formatter personalizzato che produce log in formato JSON.

    Campi principali:
    - timestamp: ISO 8601
    - level: livello di log (INFO, ERROR, ecc.)
    - logger: nome del logger
    - module: modulo sorgente
    - message: messaggio di log
    - extra: eventuali campi extra passati come extra={...}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": record.getMessage(),
        }

        # Se sono presenti eccezioni, includiamo le informazioni di stacktrace
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)

        # Fields extra definiti nel record (se presenti)
        # Attenzione a non includere attributi standard del LogRecord
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process"
        }

        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in standard_attrs
        }
        if extra_fields:
            log_record["extra"] = extra_fields

        return json.dumps(log_record, ensure_ascii=False)


def init_extensions(app: Flask) -> None:
    """
    Inizializza tutte le estensioni collegate all'app Flask.

    Questa funzione viene chiamata da create_app().
    """
    db.init_app(app)
    _init_logging(app)


def _init_logging(app: Flask) -> None:
    """
    Configura il logging applicativo:

    - handler su file con RotatingFileHandler
    - handler su console (stream)
    - formatter JSON strutturato

    Questo setup è pensato per supportare:
    - import_service (log dettagli import)
    - errori di parsing XML FatturaPA
    - errori DB
    """
    log_dir = app.config.get("LOG_DIR")
    log_file_name = app.config.get("LOG_FILE_NAME", "app.log")
    log_level_name = app.config.get("LOG_LEVEL", "INFO")

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file_name)

    # Definizione livello di log
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    # Formatter JSON
    json_formatter = JsonFormatter()

    # Handler su file (rotante)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(json_formatter)

    # Handler su console (utile in dev / container)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(json_formatter)

    # Configuriamo il logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Evita di aggiungere handler duplicati se create_app viene chiamata più volte (es. in test)
    # Puliamo gli handler esistenti solo una volta
    if not getattr(root_logger, "_json_logging_configured", False):
        # Rimuove eventuali handler pre-esistenti
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        root_logger._json_logging_configured = True  # type: ignore[attr-defined]

    # Logger specifico per l'app Flask
    app.logger.setLevel(log_level)

    app.logger.info(
        "Logging JSON inizializzato.",
        extra={
            "component": "logging",
            "log_path": log_path,
            "level": log_level_name,
        },
    )

    # (Opzionale) ridurre verbosità dei log SQLAlchemy in produzione
    # logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
