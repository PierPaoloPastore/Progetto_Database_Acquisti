# Architecture

## Stack

- Python 3.12
- Flask (app monolitica)
- SQLAlchemy (ORM)
- MySQL (mysql+pymysql)
- Jinja2 templates
- lxml per parsing XML FatturaPA
- Logging JSON con RotatingFileHandler

---

## Layer principali

### 1. Config & App Factory

- `config.py`  
  - classi `Config` / `DevConfig` / `ProdConfig` (URI MySQL, cartelle import/storage, logging).
- `manage.py`, `run_app.py`  
  - entrypoint per sviluppo e produzione.
- `app/__init__.py`  
  - `create_app`, init estensioni, middleware `auth_stub`, registrazione blueprint e healthcheck.

### 2. Estensioni & Middleware

- `app/extensions.py`  
  - istanza `db` (SQLAlchemy),
  - configurazione logging JSON su file + console (RotatingFileHandler + JsonFormatter).
- `app/middleware/auth_stub.py`  
  - utente fittizio in `g.current_user` per semplificare i template e le note.

### 3. Domain Model

`app/models/*` contiene i modelli SQLAlchemy che rappresentano il dominio del ciclo passivo:

- **Anagrafiche**
  - `Supplier`  
    Fornitore esterno (ragione sociale, P.IVA/CF, contatti).  
    **Nota:** `tax_code` rinominato in `fiscal_code`.
  - `LegalEntity`  
    Intestatario interno (società/partita IVA dell'azienda).  
    **Nota:** colonna `tax_code` rimossa (era sempre NULL).

- **Documenti di acquisto (SUPERTIPO)**
  - `Document`  
    **Supertipo unificato** per tutti i documenti economici:
    - `document_type`: discriminatore (`'invoice'`, `'f24'`, `'insurance'`, `'mav'`, `'cbill'`, `'receipt'`, `'rent'`, `'tax'`, `'other'`)
    - Colonne comuni: supplier, legal_entity, date, importi, stato
    - Colonne specifiche per tipo (nullable): `invoice_type`, `f24_payment_code`, `insurance_policy_number`, ecc.
    - Pattern: **Single Table Inheritance**
  
  - `InvoiceLine`  
    Righe fattura, collegate a `Document` (solo per `document_type='invoice'`).  
    FK: `document_id` → `documents.id`
  
  - `VatSummary`  
    Riepilogo aliquote IVA per fattura.  
    FK: `document_id` → `documents.id`
  
  - `RentContract`  
    Contratti di affitto (generano documenti mensili in `documents` con `document_type='rent'`).

- **Categorie e note**
  - `Category`  
    Categorie di spesa per righe fattura.
  - `Note`  
    Note operative collegate a `Document` (qualsiasi tipo) e `User`.  
    FK: `document_id` → `documents.id`

- **Scadenze e pagamenti**
  - `Payment`  
    Rappresenta una **scadenza** di un documento (qualsiasi tipo):
    - FK: `document_id` → `documents.id`
    - `due_date`, `expected_amount`, `paid_amount`, `paid_date`, `status`
  
  - `PaymentDocument`  
    PDF dei movimenti bancari (bonifici, MAV, assegni, ecc.).  
    **Novità:** ora ha `supplier_id` per facilitare riconciliazione.
  
  - `PaymentDocumentLink`  
    Tabella ponte M:N tra `Payment` e `PaymentDocument` per allocare un bonifico a più scadenze.

- **DDT / Bolle**
  - `DeliveryNote`  
    DDT attesi (da XML fatture differite) e reali (PDF importati).  
    FK: `document_id` → `documents.id` (solo per fatture differite)

- **Logging e impostazioni**
  - `ImportLog`  
    Log dei file XML/PDF importati.  
    FK: `document_id` → `documents.id`
  
  - `AppSetting`  
    Key/value configurabili a runtime.
  
  - `User`  
    Utenti dell'applicazione.
### 4. Persistence Layer (Repositories)

`app/repositories/*` contiene funzioni atomiche per accedere al DB in modo strutturato:

- `invoice_repository` (principale)  
  - ricerca fatture con filtri complessi (fornitore, intestatario, anno, stato doc, stato pagamento, importi, ecc.),
  - creazione fatture complete da DTO (inclusi `InvoiceLine`, `VatSummary`, `Payment` iniziali),
  - recupero fatture per revisione, gestione copie fisiche, estratto conto fornitori.
- `supplier_repo`, `legal_entity_repo`  
  - gestione anagrafiche, lookup P.IVA/CF, creazione se mancante.
- `payment_repo`  
  - gestione `Payment` (scadenze), lettura/aggiornamento stato, ricerca scadenze aperte/scadute.
- `payment_document_repo` (separato o integrato in `payment_repo`)  
  - gestione `PaymentDocument` (inbox PDF pagamenti).
- `delivery_note_repo`  
  - gestione `DeliveryNote` (DDT attesi da XML e reali da PDF, matching).
- `category_repo`, `invoice_line_repo`, `vat_summary_repo`, `notes_repo`, `import_log_repo`  
  - CRUD e query specifiche per i rispettivi modelli.

I repository incapsulano le query SQLAlchemy e centralizzano la logica di accesso ai dati; il commit è gestito dai servizi o dal `unit_of_work`.

### 5. Business Logic (Services)

`app/services/*` contiene la logica applicativa:

- `import_service`
  - import batch dei file XML FatturaPA da cartella configurata,
  - parsing XML → DTO,
  - creazione/aggiornamento `Supplier` e `LegalEntity`,
  - creazione `Invoice` + `InvoiceLine` + `VatSummary` + scadenze iniziali in `Payment`,
  - creazione dei `DeliveryNote` attesi per fatture differite,
  - scrittura `ImportLog` e logging strutturato,
  - commit/rollback per file.

- `invoice_service`
  - ricerca fatture per la UI (filtri complessi),
  - caricamento dettaglio fattura con relazioni (righe, IVA, pagamenti, DDT, note),
  - aggiornamento `doc_status`, `due_date`, `physical_copy_status`,
  - flusso di revisione delle fatture importate,
  - gestione delle copie fisiche (integrazione con `scan_service`),
  - gestione e supporto al collegamento DDT ↔ fattura (usando `DeliveryNote`).

- `payment_service`
  - gestione scadenziario basato su `Payment`:
    - creazione scadenze,
    - aggiornamento importi pagati,
    - aggiornamento `status` (`planned`, `pending`, `partial`, `paid`, ecc.),
  - import e gestione `PaymentDocument` (PDF di pagamenti reali),
  - matching tra `Payment` e `PaymentDocument` (via `PaymentDocumentLink` quando usato).

- `supplier_service`
  - liste fornitori con statistiche,
  - dettaglio fornitore con fatture collegate,
  - estratto conto per fornitore/legal entity basato su fatture + scadenze/pagamenti.

- `category_service`
  - CRUD categorie,
  - assegnazione singola/multipla di `Category` alle `InvoiceLine`.

- `scan_service`
  - gestione file sul filesystem per:
    - copie fisiche fatture,
    - DDT reali (PDF),
    - documenti di pagamento bancari,
  - naming strutturato e percorsi basati su `AppSetting`.

- `settings_service`
  - lettura/scrittura delle impostazioni applicative (`AppSetting`).

- `unit_of_work`
  - context manager per garantire commit/rollback transazionali tra più repository/servizi.

### 6. Parsing Layer

- `app/parsers/fatturapa_parser.py`
  - definisce i DTO (`InvoiceDTO`, `SupplierDTO`, `InvoiceLineDTO`, `PaymentDTO`, `VatSummaryDTO`, ecc.),
  - effettua il parsing della struttura FatturaPA:
    - testata fattura,
    - righe,
    - riepilogo IVA,
    - scadenze principali,
    - riferimenti DDT per fatture differite,
  - restituisce DTO pronti per l’uso in `import_service`.

Il layer di parsing è isolato dal resto del dominio: legge XML FatturaPA e non si occupa di come i dati vengono poi salvati.

### 7. Web & API Layer

- `app/web/*`
  - blueprint per:
    - `routes_main.py` (dashboard),
    - `routes_invoices.py` (liste, dettaglio, revisione, copie fisiche),
    - `routes_suppliers.py` (fornitori + estratti conto),
    - `routes_categories.py` (categorie e assegnazioni),
    - `routes_import.py` (import XML),
    - `routes_export.py` (export CSV),
    - `routes_settings.py` (impostazioni),
    - `routes_payments.py` (scadenziario, inbox pagamenti),
    - eventuali schermate per `delivery_notes` (inbox DDT PDF, matching con fatture).
  - pattern: route → parsing input/querystring → chiamata service/repository → render template.

- `app/api/*`
  - API JSON per:
    - aggiornare stato/due_date fattura,
    - assegnare/rimuovere categorie,
    - eventuali endpoint per aggiornare pagamenti, DDT, note.

### 8. Templates & Static

- `app/templates/*`
  - Jinja templates per:
    - liste e dettaglio fatture,
    - flusso di revisione,
    - gestione copie fisiche,
    - scadenziario e pagamenti,
    - gestione DDT,
    - fornitori, categorie, impostazioni.

- `app/static/*`
  - CSS, JS e asset condivisi (filtri, tabelle, form, ecc.).

---

## Nota sul dominio e sulle estensioni future

Ad oggi il dominio è ancora centrato su `Invoice` come oggetto economico principale, ma:

- i **pagamenti** sono modellati con un livello dedicato (`Payment` + `PaymentDocument`),
- i **DDT/bolle** sono modellati con `DeliveryNote` che unifica DDT attesi da XML e DDT reali da PDF,
- il sistema è pensato per accogliere altri documenti economici (assicurazioni, F24, scontrini, CBILL, MAV, affitti, tributi) sfruttando gli stessi meccanismi di:
  - scadenze,
  - documenti di pagamento,
  - anagrafiche fornitori/intestatari,
  - DDT/logistica quando presente.

Quando si progettano nuove feature, è importante:

- non legare troppo strettamente concetti generali (pagamento, DDT, documento PDF) a `Invoice`,
- mantenere chiara la separazione tra:
  - **import/parsing** (XML, PDF),
  - **dominio** (fatture, DDT, scadenze),
  - **servizi applicativi**,
  - **presentazione** (UI/API).
