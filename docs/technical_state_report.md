# Report tecnico stato attuale

Ultimo aggiornamento analisi: 2026-08-24

## Scopo

Questo documento fotografa lo stato tecnico attuale del repository `Gestionale Acquisti`.
L'analisi e' descrittiva: non propone refactoring e non modifica il comportamento
applicativo.

Fonti consultate:

- `docs/00_INDEX.md`
- `docs/architecture.md`
- `docs/database.md`
- `docs/CONTEXT_FOR_LLM.md`
- `README.md`
- `docs/internal_api_delivery_notes.md`
- `docs/FITOFARMACI_INTEGRATION_SOURCE.md`
- codice in `app/`, `config.py`, `Dockerfile`, `docker-compose.yml`, `manage.py`

## Struttura generale e architettura

Il progetto e' una applicazione monolitica Flask per la gestione del ciclo passivo
aziendale: import documenti, revisione, copie fisiche, scadenze, pagamenti, DDT,
classificazione e reportistica.

La struttura principale e':

- `app/__init__.py`: app factory, inizializzazione estensioni, middleware,
  registrazione blueprint e route `/health`.
- `app/models/`: modelli SQLAlchemy.
- `app/repositories/`: accesso al database tramite repository.
- `app/services/`: logica applicativa, orchestrazione, transazioni, import, file,
  OCR, pagamenti e report.
- `app/parsers/`: parser FatturaPA XML/P7M.
- `app/web/`: route HTML/Jinja.
- `app/api/`: endpoint JSON e API interne.
- `app/templates/`: template Jinja.
- `app/static/`: CSS e JavaScript.
- `resources/`: XSD, XSL e PDF di riferimento FatturaPA.
- `data/`, `storage/`, `logs/`, `import_debug/`: aree operative/generate.
- `docs/`: documentazione architetturale e operativa.
- `scripts/`: script puntuali, inclusa una migrazione SQL storica.
- `tests/`: test pytest presenti in modo limitato.

Il pattern dichiarato e' Repository + Unit of Work. I repository incapsulano query
e persistenza, mentre `app/services/unit_of_work.py` coordina commit e rollback.

## Stack tecnologico e dipendenze principali

Dipendenze principali da `requirements.txt`:

- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- Jinja2
- PyMySQL
- lxml
- cryptography
- xsdata
- python-dotenv

Dipendenze opzionali o operative:

- pytesseract
- Pillow
- pdf2image
- pypdf
- weasyprint
- wkhtmltopdf, rilevato via binario esterno se disponibile
- OpenSSL, usato come fallback esterno per P7M
- Tesseract e Poppler per OCR locale

La documentazione indica Python 3.12, mentre il `Dockerfile` usa
`python:3.10-slim`. Questa e' una discrepanza tra documentazione/runtime container.

## Database, ORM e principali entita'

L'ORM usato e' Flask-SQLAlchemy sopra SQLAlchemy, con database MySQL tramite
driver PyMySQL (`mysql+pymysql`).

Il modello centrale e' `Document`, tabella `documents`, che funge da supertipo
unificato per documenti economici. Il discriminatore e' `document_type`.

Tipi documento documentati e gestiti:

- `invoice`
- `credit_note`
- `f24`
- `insurance`
- `mav`
- `cbill`
- `receipt`
- `rent`
- `tax`
- `other`

Entita' principali:

- `Supplier`: fornitori, partita IVA/codice fiscale, contatti, IBAN, regole
  scadenza tipiche.
- `LegalEntity`: intestatari aziendali interni.
- `BankAccount`: conti bancari collegati a `LegalEntity`.
- `Document`: documento economico centrale.
- `DocumentLine`: righe documento, su tabella `invoice_lines`.
- `VatSummary`: riepiloghi IVA.
- `Payment`: scadenze e stato pagamento.
- `PaymentDocument`: PDF/metadati del movimento bancario.
- `CreditNoteAllocation`: compensazione tra nota di credito e documento da saldare.
- `DeliveryNote`: DDT attesi o importati.
- `DeliveryNoteLine`: righe DDT.
- `Category`: categorie gestionali assegnabili alle righe documento.
- `Note`: note operative su documenti.
- `ImportLog`: log import file.
- `DocumentAuditLog`: audit modifiche documenti.
- `AppSetting`: impostazioni runtime key/value.
- `User`: anagrafica utente minimale.
- `RentContract`: contratti di affitto collegabili a documenti `rent`.

Lo schema documentato include anche `payment_document_links` come tabella ponte
M:N tra `payment_documents` e `payments`, anche se il flusso web corrente usa
soprattutto `payments.payment_document_id`.

## Autenticazione e autorizzazione

L'autenticazione web attuale e' uno stub in `app/middleware/auth_stub.py`.

Comportamento:

- ogni richiesta riceve sempre `g.current_user`;
- l'utente e' un oggetto demo costante;
- non ci sono redirect, 401 o controlli reali sulle route web;
- `current_user` e' esposto ai template Jinja.

Non sono stati trovati controlli tipo `login_required`, policy centralizzate,
CSRF applicativo o enforcement dei ruoli sulle blueprint web.

L'unica autorizzazione effettiva individuata e' su:

- `POST /api/internal/delivery-notes`

Questo endpoint verifica un token configurato tramite variabile d'ambiente
`INTERNAL_API_TOKEN`, accettato con header `Authorization: Bearer ...` oppure
`X-Internal-API-Key`.

## Gestione utenti, ruoli e permessi

Il modello `User` contiene:

- `username`
- `full_name`
- `email`
- `role`
- `is_active`
- timestamp di creazione/aggiornamento

I ruoli documentati sono:

- `admin`
- `user`
- `readonly`

Nel codice attuale questi ruoli sono dati persistiti ma non risultano applicati
come controlli di accesso. Il campo `is_admin` dell'auth stub e' sempre riferito
all'utente demo e non deriva dal database.

Le note (`Note`) possono collegarsi a `User`, ma l'autenticazione corrente non
recupera un utente reale dal database.

## Principali route e API

Route web principali:

- `/`: dashboard.
- `/documents`: lista documenti, filtri, dettaglio, audit, revisione, creazione
  manuale, preview, download XML/P7M/PDF, copia fisica, matching DDT,
  aggiornamento stato, conferma e archiviazione.
- `/import/run`: import FatturaPA da upload o cartella server.
- `/payments`: dashboard pagamenti, pagamenti batch, cronologia, allegati,
  OCR e dettaglio pagamento.
- `/payments/schedule`: scadenziario pagamenti.
- `/payments/schedule/cbi`: export XML SEPA/CBI pain.001.
- `/payments/schedule/print`: stampa PDF dello scadenziario.
- `/delivery-notes`: lista, creazione, dettaglio, righe, file, OCR e matching DDT.
- `/suppliers`: anagrafiche fornitori e report CSV.
- `/legal-entities`: intestatari e conti bancari.
- `/categories`: categorie e assegnazioni massive.
- `/export/invoices`: export CSV fatture.
- `/reports`: reportistica mensile, stati, categorie e fornitori.
- `/settings`: impostazioni applicative e manutenzione database.
- `/help`: guide operative.

API JSON principali:

- `POST /api/documents/<document_id>/status`: aggiorna stato documento e
  scadenza.
- `POST /api/documents/lines/<line_id>/category`: assegna o rimuove categoria
  da una riga.
- `GET /api/categories/`: lista categorie attive.
- `POST /api/categories/bulk-assign`: assegna categoria a piu' righe.
- `POST /api/internal/delivery-notes`: crea DDT da sistema interno esterno.

## Gestione e archiviazione documenti/file

La gestione file e' filesystem-based con percorsi configurabili.

Storage principali:

- XML/P7M importati: `XML_STORAGE_PATH`, fallback `storage/xml`.
- Copie fisiche documenti: `PHYSICAL_COPY_STORAGE_PATH`, fallback
  `storage/documenti`.
- PDF pagamenti: `PAYMENT_FILES_STORAGE_PATH`, fallback `storage/pagamenti`.
- PDF DDT: `DELIVERY_NOTE_STORAGE_PATH`, fallback `storage/ddt`.
- Allegati: `ATTACHMENTS_STORAGE_PATH`, fallback `storage/attachments`.

I percorsi possono arrivare da:

- variabili/config Flask;
- tabella `app_settings`, gestita dal servizio `settings_service`;
- fallback locali.

Flussi file principali:

- Import XML/P7M: copia nello storage XML organizzato per anno e spostamento
  dell'originale in `Archivio/XML/<anno>`.
  I nuovi import usano nel deposito il nome `AAAA-MM-GG_Fornitore_Numero.xml`
  (estensione originale XML/P7M preservata), con caratteri normalizzati e suffisso
  numerico in caso di collisione. Gli XML con piu fatture usano i dati della prima
  e il suffisso `_multi`; senza data o numero si usano `senza-data` e `senza-numero`.
  Il nome originale resta nell'archivio e in `documents.file_name`; il nuovo
  percorso viene salvato in `documents.file_path`. File storici e import con
  parsing incompleto mantengono il nome precedente. Anche i download continuano
  a proporre il nome originale.
  Per esempi, regole complete e verifiche consultare la
  [guida al deposito XML e al naming](guides/xml_storage_naming.md).
- Copie fisiche: salvataggio path relativo in `documents.physical_copy_file_path`.
- Pagamenti: salvataggio PDF in storage pagamenti e copia in
  `Archivio/Pagamenti/<anno>`.
- DDT: salvataggio file in storage DDT e copia in `Archivio/DDT/<anno>`.
- Report import: CSV in `import_debug/import_reports`.

Le route usano `send_file` per servire sorgenti XML/P7M, PDF renderizzati,
copie fisiche, DDT e file pagamento.

## Integrazioni con servizi esterni

Integrazioni operative individuate:

- MySQL come database applicativo.
- OCR locale con Tesseract, Poppler, pytesseract, pdf2image, Pillow e pypdf.
- OCRSpace opzionale via HTTP, configurato con `OCR_PROVIDER`,
  `OCRSPACE_API_KEY` e `OCRSPACE_ENDPOINT`.
- OpenSSL come fallback per estrazione XML da P7M.
- wkhtmltopdf o WeasyPrint per generazione PDF.
- Endpoint interno per `GestionaleFitofarmaci`, tramite creazione DDT.
- Export bancario SEPA/CBI pain.001 generato localmente, senza chiamata API
  bancaria.

La documentazione `FITOFARMACI_INTEGRATION_SOURCE.md` descrive anche un possibile
consumo read-only del database da parte di un futuro sistema Fitofarmaci.

## Docker e deployment

Il `Dockerfile`:

- usa `python:3.10-slim`;
- installa librerie di sistema per MySQL, XML/XSL, immagini/PDF e WeasyPrint;
- installa `requirements.txt`;
- copia il repository in `/app`;
- espone porta `5000`;
- avvia `python manage.py runserver`.

Il `docker-compose.yml`:

- definisce servizio `web`;
- espone `8081:5000`;
- monta `/mnt/pastore:/mnt/pastore`;
- usa network esterna `gestionale-network`;
- imposta variabili d'ambiente DB;
- esegue il container come utente `0:0`.

Non risultano configurati:

- Gunicorn/uWSGI;
- healthcheck Docker;
- pipeline CI/CD;
- migrazioni automatiche;
- secrets manager;
- job di backup o restore.

## Configurazioni, secret e variabili d'ambiente

Variabili/config principali lette da `config.py`:

- `SECRET_KEY`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `DB_NAME`
- `DATABASE_URL`
- `UPLOAD_FOLDER`
- `IMPORT_XML_FOLDER`
- `LOG_DIR`
- `LOG_LEVEL`
- `LOG_FILE_NAME`

Variabili/setting ulteriori individuati:

- `FLASK_RUN_HOST`
- `FLASK_RUN_PORT`
- `INTERNAL_API_TOKEN`
- `TESSERACT_CMD`
- `POPPLER_PATH`
- `OPENSSL_BIN`
- `WKHTMLTOPDF_BIN`
- `OCR_PROVIDER`
- `OCRSPACE_API_KEY`
- `OCRSPACE_ENDPOINT`
- `OCR_DEFAULT_LANG`
- `OCR_MAX_PAGES`
- `PHYSICAL_COPY_STORAGE_PATH`
- `XML_STORAGE_PATH`
- `PAYMENT_FILES_STORAGE_PATH`
- `DELIVERY_NOTE_STORAGE_PATH`
- `ATTACHMENTS_STORAGE_PATH`
- `IMPORT_DDT_FROM_XML`
- `DEFAULT_XSL_STYLE`
- `SCHEDULE_SOON_DAYS`
- `SCHEDULE_GROUP_BY_SUPPLIER`
- `FORMAT_THOUSANDS_SEPARATOR`

Nota di stato: sono presenti fallback hardcoded per credenziali/configurazioni
sensibili in file versionati. I valori non sono riportati in questo documento.

## Servizi/processi asincroni o schedulati

Non sono stati trovati worker Celery, RQ, APScheduler, cron o servizi schedulati
nel repository.

L'import FatturaPA usa un `threading.Lock` in-process per evitare esecuzioni
concorrenti nello stesso processo Python.

Le sincronizzazioni notturne o event-driven citate nella documentazione
Fitofarmaci sono descritte come ipotesi future, non come processi implementati.

## Backup

Non e' stato trovato un sistema di backup database:

- nessuno script `mysqldump`;
- nessuna procedura restore;
- nessun backup schedulato;
- nessuna strategia di retention dati DB.

Sono presenti meccanismi di archiviazione file:

- `Archivio/XML/<anno>`;
- `Archivio/Documenti/<anno>`;
- `Archivio/Pagamenti/<anno>`;
- `Archivio/DDT/<anno>`.

Questi archivi sono copie/spostamenti documentali, non backup transazionali
dell'applicazione.

Il logging usa rotazione con `backupCount=3`, ma riguarda solo i file log.

## Logging e gestione errori

Il logging e' configurato in `app/extensions.py`:

- formatter JSON custom;
- `RotatingFileHandler`;
- handler console;
- dimensione file log massima 5 MB;
- 3 file di rotazione;
- livello configurabile con `LOG_LEVEL`.

Gli import producono log strutturati e report CSV. Il parser FatturaPA gestisce
errori XML/P7M con fallback e dump diagnostici in `import_debug` in alcuni casi.

Le route web usano prevalentemente `flash` e redirect per errori applicativi.
Le API JSON restituiscono payload con `success`, `message` e `payload`, con status
HTTP dedicati nei casi principali.

Alcune aree catturano eccezioni generiche per mantenere continuita' operativa,
in particolare import, OCR, settings e route web.

## Accoppiamenti rilevanti per SSO o integrazioni aziendali

Punti che possono rendere complessa una integrazione con autenticazione
centralizzata o altri applicativi:

- Le route web non hanno autenticazione reale: serve definire protezione per
  tutte le blueprint, gestione sessione e identity provider.
- Il modello `User` e i ruoli non sono collegati a policy applicative effettive.
- Operazioni sensibili sono spesso protette da conferme testuali, non da
  autorizzazioni.
- I file sono gestiti su filesystem/mount condivisi con path salvati nel DB.
- La configurazione e' distribuita tra env vars, `config.py`, fallback locali e
  `app_settings`.
- Alcuni nomi e flussi conservano semantica legacy `invoice`, pur usando
  `Document` come supertipo.
- L'integrazione Fitofarmaci documentata prevede letture SQL dirette read-only:
  approccio semplice, ma accoppiato allo schema DB.
- Le API JSON coprono solo una parte del dominio; molte operazioni sono esposte
  solo come route server-rendered.
- Non sono presenti migrazioni formali tipo Alembic; esistono `db.create_all()`
  e script SQL puntuali.
- L'accesso a download/preview file dipende dalle route web non autenticate.

## Schema testuale componenti e flussi principali

```text
Browser / UI Jinja
  -> app/web blueprints
     -> app/services
        -> app/repositories / UnitOfWork
           -> SQLAlchemy ORM
              -> MySQL

API JSON
  -> /api/documents
  -> /api/categories
  -> /api/internal/delivery-notes [INTERNAL_API_TOKEN]
     -> delivery_note_service
        -> MySQL
        -> storage DDT

Import FatturaPA
  -> /import/run
     -> import_service
        -> fatturapa_parser_v2 [xsdata]
        -> fallback fatturapa_parser [lxml/OpenSSL]
        -> Supplier / LegalEntity
        -> Document / DocumentLine / VatSummary
        -> Payment
        -> DeliveryNote attesi da XML
        -> ImportLog
        -> storage/xml
        -> Archivio/XML
        -> import_debug/import_reports

Documenti
  -> /documents
     -> document_service
        -> Document
        -> righe, IVA, note, audit, pagamenti, DDT
        -> physical copy storage
        -> preview XSL
        -> PDF rendering

Pagamenti
  -> /payments
  -> /payments/schedule
     -> payment_service
        -> Payment
        -> PaymentDocument
        -> CreditNoteAllocation
        -> storage pagamenti
        -> Archivio/Pagamenti
        -> CBI XML pain.001
        -> OCR opzionale

DDT
  -> /delivery-notes
  -> /api/internal/delivery-notes
     -> delivery_note_service
        -> DeliveryNote
        -> DeliveryNoteLine
        -> storage DDT
        -> Archivio/DDT
        -> matching con Document

Configurazione
  -> env vars
  -> config.py
  -> AppSetting DB
  -> /settings
  -> percorsi storage/log
```

## Verifica

Questa analisi e' stata prodotta con lettura del repository e senza avviare
servizi o modificare codice applicativo.
