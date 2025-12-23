# Progetto Database Acquisti

Nota: documento storico. Il parsing FatturaPA attuale usa xsdata come percorso principale con fallback legacy e pulizia dei tag P7M; vedi `docs/architecture.md` e `docs/fatturapa/PARSING_REFERENCE.md`.

## Panoramica del Progetto

**Progetto Database Acquisti** è un'applicazione web basata su Flask per la gestione completa del ciclo di vita dei documenti di acquisto (principalmente fatture elettroniche italiane FatturaPA) e del ciclo passivo per un'azienda.

## Stack Tecnologico

- **Backend**: Python 3.12, Flask 3.0
- **Database**: MySQL 8.x (mysql+pymysql)
- **ORM**: SQLAlchemy
- **Template Engine**: Jinja2
- **Parsing XML**: xsdata + lxml (legacy fallback) per FatturaPA
- **Logging**: JSON structured logging con RotatingFileHandler

## Architettura

Il progetto segue un'architettura a livelli (Layered Architecture) con chiara separazione delle responsabilità:

```
/home/user/Progetto_Database_Acquisti/
├── app/
│   ├── models/           # Modelli di dominio (SQLAlchemy ORM)
│   ├── repositories/     # Data access layer
│   ├── services/         # Business logic layer
│   ├── parsers/          # Parsing XML FatturaPA
│   ├── web/              # Route web (blueprints)
│   ├── api/              # API endpoints JSON
│   ├── templates/        # Template HTML Jinja2
│   ├── static/           # Asset CSS/JS
│   ├── middleware/       # Auth stub (current user injection)
│   └── extensions.py     # Configurazione DB e logging
├── config.py             # Configurazioni per ambiente
├── manage.py             # Comandi CLI
├── run_app.py            # Entry point produzione
└── requirements.txt      # Dipendenze
```

### Pattern Architetturali Chiave

- **Repository Pattern**: Isolamento dell'accesso ai dati
- **Service Layer**: Logica di business centralizzata
- **Unit of Work**: Gestione transazioni
- **DTO (Data Transfer Objects)**: Trasferimento dati tra layer
- **Single Table Inheritance**: Per la gestione unificata dei documenti

## Modifiche Recenti (Ultimi 5 Commit)

### Refactoring Maggiore: "Da Fatture a Documenti"

Il progetto ha recentemente completato una trasformazione architettonica significativa:

**Cosa è cambiato:**

1. **Refactoring del Modello Database**
   - Migrazione da tabelle specifiche per fatture a un supertipo unificato `documents`
   - Utilizzo di Single Table Inheritance (STI) con discriminatore `document_type`
   - Vecchio: tabella `invoices`
   - Nuovo: tabella `documents` con supporto per multiple tipologie

2. **Rinominazioni nel Codebase**
   - Route: `/invoices` → `/documents`
   - File: `routes_invoices.py` → `routes_documents.py`
   - API: `api_invoices.py` → `api_documents.py`
   - Template: cartella `invoices/` → `documents/`
   - Aggiornamento registrazioni blueprint

3. **Redesign UI (Commit: 0dc4059)**
   - Riprogettazione pagina dettaglio fornitori
   - Aggiornamento UI pagamenti
   - Correzione route pagamenti

4. **Gestione Scansioni e Stati Pagamento (Commit: 08a8a8a)**
   - Refactoring flusso allegati scansioni con upload diretto
   - Aggiornamento logica stati pagamento (stati 'partial' e 'reconciled')
   - Miglioramento validazione form e UI

**Statistiche del Refactoring:**
- 36 file modificati
- +1,814 inserzioni, -1,243 eliminazioni

## Funzionalità Principali

### A. Importazione e Gestione Documenti

- Importazione XML FatturaPA da cartella configurata
- Supporto P7M (XML firmati) con estrazione automatica
- Parsing robusto con fallback encoding (UTF-8, windows-1252)
- Parsing automatico di:
  - Header documento (numero, data, importi)
  - Righe fattura (codice articolo, quantità, prezzo, IVA)
  - Riepiloghi IVA
  - Condizioni di pagamento e scadenze
  - Riferimenti DDT (per fatture differite)

### B. Workflow di Revisione Documenti

- Coda di revisione per documenti importati
- Tracciamento stato: `imported` → `verified` → `archived`/`rejected`
- Gestione copie fisiche:
  - Richiesta, ricezione, upload copie scansionate
  - Stati: `missing`, `requested`, `received`, `uploaded`, `not_required`

### C. Pagamenti e Scadenze

- Calendario pagamenti unificato per tutti i tipi di documento
- Tracciamento pagamenti con stati: `unpaid`, `planned`, `pending`, `partial`, `paid`, `overdue`
- Inbox documenti di pagamento (import PDF bonifici, MAV, assegni)
- Riconciliazione tra scadenze e documenti di pagamento
- Relazione M:N (un pagamento può coprire multiple scadenze)

### D. Gestione DDT (Documenti di Trasporto)

- Tracciamento DDT attesi da fatture differite
- Import DDT fisici come PDF
- Sistema di matching: `unmatched`, `matched`, `missing`

### E. Gestione Anagrafiche

- Fornitori (`suppliers`) con codice fiscale/P.IVA univoco
- Entità legali (`legal_entities`) - entità interne dell'azienda
- Categorie per classificazione spese
- Note interne sui documenti

### F. Ricerca e Reportistica

- Filtri avanzati (fornitore, intervallo date, stato, importi, anno)
- Estratti conto fornitori
- Riepiloghi IVA
- Export CSV per contabilità esterna

## Architettura Database: Single Table Inheritance

Il sistema utilizza un approccio **supertipo unificato**:

```
documents (tabella singola)
├── Colonne comuni (tutti i tipi di documento)
├── document_type (discriminatore)
│   ├── 'invoice' (FatturaPA)
│   ├── 'f24' (modello F24)
│   ├── 'insurance' (polizze assicurative)
│   ├── 'mav' / 'cbill' (avvisi di pagamento)
│   ├── 'receipt' (ricevute)
│   ├── 'rent' (contratti di locazione)
│   ├── 'tax' (imposte/tributi)
│   └── 'other'
└── Colonne specifiche per tipo (nullable)
```

### Tabelle Principali

- `documents` - Supertipo universale per documenti (45+ colonne)
- `invoice_lines` - Righe fattura (solo per fatture)
- `vat_summaries` - Riepiloghi IVA (solo per fatture)
- `payments` - Scadenze/registrazioni pagamenti (TUTTI i tipi di documento)
- `payment_documents` - PDF pagamenti bancari
- `delivery_notes` - DDT/documenti di trasporto
- `suppliers` - Fornitori esterni
- `legal_entities` - Entità aziendali interne
- `categories` - Categorie di spesa
- `notes` - Note interne sui documenti
- `import_logs` - Audit trail importazioni
- `rent_contracts` - Contratti di locazione (genera documenti mensili)

### Vincoli Database

- Constraint CHECK su tutti gli ENUM
- Constraint condizionali (es: invoice_type solo per document_type='invoice')
- Constraint UNIQUE su partite IVA
- Regole di cascade per foreign key

## Stato Attuale dell'Applicazione

### Status: Production-Ready con Sviluppo Attivo

**Funzionalità Completamente Operative:**

1. Import FatturaPA (XML e P7M)
2. Workflow di revisione documenti
3. Schedulazione pagamenti
4. Gestione fornitori
5. Assegnazione categorie
6. Export CSV
7. Tracciamento copie fisiche

**Schema Pronto, Implementazione Pending:**

- F24 (moduli fiscali) - colonne esistenti, logica import necessaria
- Polizze assicurative - colonne esistenti, logica import necessaria
- Avvisi MAV/CBILL - colonne esistenti, logica import necessaria
- Contratti locazione - colonne esistenti, generazione ricorrente necessaria
- Ricevute - colonne esistenti, import OCR necessario

### Struttura Route

- `/` - Dashboard
- `/documents/*` - Gestione documenti
- `/suppliers/*` - Gestione fornitori
- `/categories/*` - Gestione categorie
- `/payments/*` - Calendario pagamenti e inbox
- `/import/*` - Interfaccia import XML
- `/export/*` - Export CSV
- `/settings/*` - Impostazioni app
- `/api/documents/*` - API JSON
- `/api/categories/*` - API JSON

### Frontend

- Rendering server-side con Jinja2
- JavaScript minimale (filtri, assegnazione categorie)
- CSS organizzato per concern (main, forms, tables, compact)
- Layout responsive ma non mobile-first

## Qualità del Codice

- Commenti e documentazione in italiano (intenzionale)
- Utilizzo features Python 3.12+
- Type hints nella maggior parte delle funzioni service/repository
- Docstring comprensivi
- Structured logging (formato JSON)

## Configurazione

- Config basata su environment (DevConfig/ProdConfig)
- Connessione MySQL via variabili d'ambiente
- Cartelle di import configurabili
- Log rotativi in directory `/logs`

## Debito Tecnico Noto

- Alcuni service usano ancora `db.session.commit()` diretto invece di UnitOfWork (documentato in db_commit_audit.md)
- Autenticazione è stubbed (necessita implementazione reale)
- Nessun test automatizzato visibile nel repository
- Alcune terminologie legacy "invoice" rimangono nelle variabili template per compatibilità

## Roadmap Futura

Secondo FUTURE_DOCUMENT_TYPES.md:

- **Priorità Alta (Q1 2026)**: F24, Assicurazioni
- **Priorità Media (Q2 2026)**: MAV/CBILL, Locazioni ricorrenti, OCR ricevute
- **Priorità Bassa (Q3-Q4 2026)**: Contratti manutenzione, utenze, pedaggi, carburante

## Documentazione Disponibile

Il progetto include 7 file markdown con documentazione dettagliata:

- Architettura generale
- Schema database
- Troubleshooting
- Audit commit database
- Tipi di documento futuri

## Conclusione

Questo è un sistema ben architettato e production-ready che ha recentemente completato con successo una modernizzazione per supportare multiple tipologie di documento oltre alle fatture. Il codebase mostra una progettazione attenta con chiara separazione delle responsabilità e documentazione estensiva.

---

**Ultimo Aggiornamento**: 2025-12-10
**Branch Attivo**: claude/update-claude-md-01Hmso5FGmfYoeVytrNNab3u
**Commit Recente**: 08a8a8a - Refactor scan attachment and payment status handling
