# Gestionale Acquisti - Flask + MySQL

Nota: documento storico. Il parsing FatturaPA attuale usa xsdata come percorso principale con fallback legacy e pulizia dei tag P7M; vedi `docs/architecture.md` e `docs/fatturapa/PARSING_REFERENCE.md`.

Applicazione monolitica Flask per la gestione delle fatture di acquisto, con import da XML FatturaPA.

## Requisiti
- Python 3.10+
- MySQL 8.x
- (Opzionale) virtualenv per isolare le dipendenze

## Setup ambiente
1. (Opzionale) crea e attiva un virtualenv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate    # Linux/macOS
   # .venv\\Scripts\\activate   # Windows
   ```
2. Installa le dipendenze del progetto (include Flask, SQLAlchemy, PyMySQL, ecc.):
   ```bash
   pip install -r requirements.txt
   ```

## Configurazione database
1. Aggiorna `config.py` nella classe `DevConfig` con le tue credenziali MySQL:
   ```python
   SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:password@localhost/gestion_acquisti"
   ```
2. Assicurati che il database `gestion_acquisti` (o quello scelto) esista in MySQL e che l'utente abbia i permessi.

## Creazione tabelle
Esegui il comando CLI per generare le tabelle definite nei modelli SQLAlchemy:
```bash
python manage.py create-db
```
In caso di errori di connessione, verifica host/porta/credenziali del DB.

## Avvio del server di sviluppo
Avvia l'app Flask su host e porta predefiniti (`0.0.0.0:5000`):
```bash
python manage.py runserver
```
Puoi cambiare host/port con le variabili `FLASK_RUN_HOST` e `FLASK_RUN_PORT`.

## Risoluzione problemi comuni
- **ModuleNotFoundError: No module named 'sqlalchemy'**: assicurati di aver installato le dipendenze con `pip install -r requirements.txt` nel tuo ambiente attivo.
- **OperationalError** su MySQL: verifica che il server sia avviato, le credenziali in `config.py` siano corrette e che il DB esista.
