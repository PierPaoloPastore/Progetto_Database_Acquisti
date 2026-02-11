"""
Modulo di configurazione per l'applicazione Flask.
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Configurazione base, comune a tutti gli ambienti."""

    # Chiave segreta: in produzione deve essere sovrascritta da variabile d'ambiente
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # --- CONFIGURAZIONE DATABASE MYSQL --------------------------------------
    DB_USER = os.environ.get("DB_USER", "repartoitsql")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "giovanni$")
    DB_HOST = os.environ.get("DB_HOST", "db-magazzino-mysql-1")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ.get("DB_NAME", "gestionale_acquisti")

    # Stringa di connessione composta in modo parametrico
    DEFAULT_DB_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- GESTIONE FILE (UPLOAD & STORAGE) ------------------------------------
    # Cartella base per gli upload generici e le scansioni fisiche
    # Nota: Assicurati che questa cartella 'storage' esista nel tuo progetto
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", 
        str(BASE_DIR / "storage")
    )
    
    # Cartella specifica dove il parser cerca i file XML da importare
    IMPORT_XML_FOLDER = os.environ.get(
        "IMPORT_XML_FOLDER",
        str(BASE_DIR / "data" / "fatture_xml"),
    )

    # Limite massimo dimensione file upload (es. 16 MB)
    # Utile per evitare crash se si caricano scansioni PDF enormi
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 

    # --- LOGGING -------------------------------------------------------------
    LOG_DIR = os.environ.get("LOG_DIR", str(BASE_DIR / "logs"))
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FILE_NAME = os.environ.get("LOG_FILE_NAME", "app.log")


class DevConfig(Config):
    """Configurazione per ambiente di sviluppo."""
    DEBUG = True
    ENV = "development"
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG")


class ProdConfig(Config):
    """Configurazione per ambiente di produzione."""
    DEBUG = False
    ENV = "production"
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
