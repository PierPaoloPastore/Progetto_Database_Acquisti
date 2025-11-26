# Gestionale Acquisti - Flask + MySQL

Applicazione monolitica Flask per la gestione delle fatture di acquisto, con import da XML FatturaPA.

## Requisiti

- Python 3.10+ (consigliato)
- MySQL 8.x
- Virtualenv (opzionale ma consigliato)

## Setup ambiente

1. Clona il repository o copia i file del progetto.

2. Crea e attiva un virtualenv (opzionale ma consigliato):

   ```bash
   python -m venv .venv
   source .venv/bin/activate    # Linux/macOS
   # .venv\Scripts\activate     # Windows
Installa le dipendenze:

bash
Copia codice
pip install -r requirements.txt
Configura la connessione MySQL in config.py:

Modifica DevConfig.SQLALCHEMY_DATABASE_URI usando le tue credenziali, ad esempio:

python
Copia codice
SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:password@localhost/gestion_acquisti"
Assicurati che il database (gestion_acquisti nell'esempio) esista in MySQL.