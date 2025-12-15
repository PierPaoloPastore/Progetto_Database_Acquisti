Last updated: 2025-12-15

# Gestionale Acquisti - Flask + MySQL

Applicazione monolitica Flask per la gestione delle fatture di acquisto e, più in generale, del ciclo passivo aziendale. Il progetto gestisce l’intero ciclo di vita dei documenti di acquisto (import, revisione, copie fisiche, scadenze e pagamenti) partendo oggi dalle fatture elettroniche FatturaPA e aprendosi a nuovi tipi documentali.

## Panoramica e obiettivi

La webapp modella tutti i documenti economici su un **supertipo unificato** (`documents`) con Single Table Inheritance, così da supportare:
- Fatture FatturaPA (immediate e differite con gestione DDT)
- F24, assicurazioni, MAV, CBILL, scontrini, affitti, tributi e altri documenti economici
- Flussi comuni per revisione, scadenziario, pagamenti e controllo documentale

Funzionalità principali oggi disponibili:
- **Import e modellazione**: parsing XML/P7M FatturaPA (header, righe, riepiloghi IVA, scadenze, riferimenti DDT) con DTO dedicati.
- **Revisione e controllo**: workflow di stato (`imported`, `verified`, `rejected`, `cancelled`, `archived`) e gestione copie fisiche con tracciamento `physical_copy_status`.
- **Gestione DDT**: `delivery_notes` per DDT attesi da XML e DDT reali importati come PDF, con stato di matching.
- **Scadenze e pagamenti**: tabella `payments` con più scadenze per documento, stati (`unpaid`, `planned`, `pending`, `partial`, `paid`, `overdue`), riconciliazione con `payment_documents` e legami M:N tramite `payment_document_links`.
- **Anagrafiche e classificazione**: fornitori (`suppliers`), intestatari (`legal_entities`), categorie (`categories`) collegate alle righe (`invoice_lines`), note operative (`notes`).
- **Reporting ed export**: export CSV, riepiloghi IVA, estratti conto fornitori/legal entities, scadenziario unificato.

Direzioni di sviluppo già definite includono l’estensione a nuovi documenti (assicurazioni, F24, affitti, tributi, ecc.) mantenendo un unico flusso operativo, e il refactoring del parser verso **`xsdata`** per ottenere type safety e copertura completa degli schemi FatturaPA.

## Stack tecnico
- Python 3.12
- Flask (app monolitica)
- SQLAlchemy (ORM) su MySQL (`mysql+pymysql`)
- Jinja2 templates
- `lxml` per parsing XML/P7M FatturaPA
- Logging JSON con `RotatingFileHandler`

## Setup rapido

### Requisiti
- Python 3.10+
- MySQL 8.x
- (Opzionale) virtualenv per isolare le dipendenze

### Preparazione ambiente
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

### Configurazione database
1. Aggiorna `config.py` nella classe `DevConfig` con le tue credenziali MySQL:
   ```python
   SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:password@localhost/gestion_acquisti"
   ```
2. Assicurati che il database `gestion_acquisti` (o quello scelto) esista in MySQL e che l'utente abbia i permessi.

### Creazione tabelle
Esegui il comando CLI per generare le tabelle definite nei modelli SQLAlchemy:
```bash
python manage.py create-db
```
In caso di errori di connessione, verifica host/porta/credenziali del DB.

### Avvio del server di sviluppo
Avvia l'app Flask su host e porta predefiniti (`0.0.0.0:5000`):
```bash
python manage.py runserver
```
Puoi cambiare host/port con le variabili `FLASK_RUN_HOST` e `FLASK_RUN_PORT`.

### Risoluzione problemi comuni
- **ModuleNotFoundError: No module named 'sqlalchemy'**: assicurati di aver installato le dipendenze con `pip install -r requirements.txt` nel tuo ambiente attivo.
- **OperationalError** su MySQL: verifica che il server sia avviato, le credenziali in `config.py` siano corrette e che il DB esista.

## Documentazione
Consulta l’indice completo in [`docs/00_INDEX.md`](docs/00_INDEX.md) per architettura, database, guide, roadmap e note meta.

## Direzioni di sviluppo
- Generalizzazione del modello da "fattura" a **documento/movimento di acquisto**, mantenendo `invoices` come primo caso concreto.
- Integrazione di documenti PDF per assicurazioni, F24, MAV/CBILL, affitti e altri tributi con flussi analoghi a DDT e pagamenti.
- Automazione della riconciliazione (fatture ↔ DDT; scadenze ↔ documenti di pagamento).
- Miglioramento UX per revisione fatture, scadenziario e gestione DDT mancanti.
- **Refactoring Tecnico Parser (Versione 2.0)**: migrazione a `xsdata` per generare DTO dai XSD ufficiali FatturaPA, garantendo type safety e copertura completa dello standard.
