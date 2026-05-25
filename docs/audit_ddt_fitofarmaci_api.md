# Audit DDT per integrazione con GestionaleFitofarmaci

Data audit: 2026-05-25
Repo: `D:\Progetto_Database_Acquisti`
Ambito: analisi read-only del flusso DDT attuale e proposta per API interna di creazione DDT da un secondo gestionale esterno.

## 1. Sintesi esecutiva

Nel gestionale acquisti i DDT sono gia modellati come entita autonome tramite:

- `delivery_notes`
- `delivery_note_lines`

Il sistema supporta gia due origini:

- DDT attesi estratti dagli XML FatturaPA (`source = xml_expected`)
- DDT reali caricati via PDF dalla UI (`source = pdf_import`)

Esiste anche il valore logico/documentato `manual`.

Il punto corretto per integrare `GestionaleFitofarmaci` non e una route web, ma un nuovo endpoint API dedicato che riusi il layer `app/services/delivery_note_service.py`.

Criticita principale: le API JSON attuali non hanno una vera autenticazione applicativa. Un nuovo endpoint interno non deve copiare quel pattern, ma introdurre protezione esplicita a token.

Scelta consigliata per minimizzare impatto:

- nuovo endpoint `POST /api/internal/delivery-notes`
- auth tramite `Authorization: Bearer <token>` o `X-Internal-API-Key`
- creazione DDT standalone con `document_id = null`
- `source = manual`
- `import_source = GestionaleFitofarmaci:<external_id>`

Questo evita modifiche DB immediate e permette tracciabilita della provenienza.

## 2. Mappa file rilevanti

### Modelli

- `app/models/delivery_note.py`
- `app/models/delivery_note_line.py`
- `app/models/document.py`

### Repository

- `app/repositories/delivery_note_repo.py`
- `app/repositories/delivery_note_line_repo.py`
- `app/repositories/document_repo.py`

### Service

- `app/services/delivery_note_service.py`
- `app/services/import_service.py`
- `app/services/scan_service.py`
- `app/services/settings_service.py`

### Parser

- `app/parsers/fatturapa_parser.py`

### Route web

- `app/web/routes_delivery_notes.py`
- `app/web/routes_documents.py`

### Template Jinja

- `app/templates/delivery_notes/list.html`
- `app/templates/delivery_notes/detail.html`
- `app/templates/delivery_notes/match_document.html`
- `app/templates/documents/match_delivery_notes.html`

### API esistenti

- `app/api/api_documents.py`
- `app/api/api_categories.py`
- `app/api/__init__.py`

### Middleware/auth

- `app/middleware/auth_stub.py`

### Documentazione utile

- `docs/00_INDEX.md`
- `docs/architecture.md`
- `docs/database.md`

## 3. Modelli SQLAlchemy coinvolti nei DDT

### `DeliveryNote`

File: `app/models/delivery_note.py`

Tabella: `delivery_notes`

Campi:

- `id`
- `document_id` FK a `documents.id`
- `supplier_id` FK a `suppliers.id`
- `legal_entity_id` FK a `legal_entities.id`
- `ddt_number`
- `ddt_date`
- `total_amount`
- `file_path`
- `file_name`
- `source`
- `import_source`
- `imported_at`
- `status`
- `created_at`
- `updated_at`

Relazioni:

- `document`
- `supplier`
- `legal_entity`
- `delivery_note_lines`

Note importanti:

- il modello rappresenta sia DDT attesi da XML sia DDT reali da PDF
- `document_id` e opzionale
- `import_source` e gia disponibile per tracciare una provenienza esterna

### `DeliveryNoteLine`

File: `app/models/delivery_note_line.py`

Tabella: `delivery_note_lines`

Campi:

- `id`
- `delivery_note_id` FK a `delivery_notes.id`
- `line_number`
- `description`
- `item_code`
- `quantity`
- `uom`
- `amount`
- `notes`
- `created_at`
- `updated_at`

Relazione:

- `delivery_note`

### `Document`

File: `app/models/document.py`

Rilevanza per i DDT:

- espone relazione `delivery_notes`
- il collegamento avviene tramite `delivery_notes.document_id`
- il legame non e ristretto a una sottoclasse specifica, ma al supertipo `Document`

## 4. Tabelle DB usate per i DDT

Da codice e documentazione emergono:

- `delivery_notes`
- `delivery_note_lines`

Tabelle correlate:

- `documents`
- `suppliers`
- `legal_entities`

Dal file `docs/database.md` risultano anche:

- indice su `supplier_id`
- indice composto `(supplier_id, ddt_date, ddt_number)`
- indice su `document_id`
- indice su `status`
- unique sulle righe `(delivery_note_id, line_number)`

## 5. Righe DDT

Esiste una tabella dedicata:

- `delivery_note_lines`

Le righe sono gestite da:

- `app/repositories/delivery_note_line_repo.py`
- `app/services/delivery_note_service.py` tramite `upsert_delivery_note_lines(...)`

La UI del dettaglio DDT permette aggiunta/rimozione/modifica righe.

## 6. Flusso attuale di creazione DDT

### Flusso A: creazione manuale via UI con PDF

Entry point:

- `GET /delivery-notes/`
- `POST /delivery-notes/`

Implementazione:

- route in `app/web/routes_delivery_notes.py`
- service in `app/services/delivery_note_service.py`

Passi:

1. utente apre tab "Nuovo DDT"
2. carica un PDF
3. seleziona fornitore
4. opzionalmente seleziona intestatario
5. inserisce numero e data DDT
6. opzionalmente inserisce totale
7. submit verso `POST /delivery-notes/`
8. `create_delivery_note(...)` valida dati base e salva il file
9. viene creato record `delivery_notes`
10. redirect al dettaglio DDT

Valori tipici impostati:

- `source = pdf_import`
- `status = unmatched`
- `import_source = manual_upload`
- `imported_at = utcnow()`

### Flusso B: OCR assistito sulla UI

Entry point:

- `POST /delivery-notes/ocr`
- `POST /delivery-notes/ocr-map`

Uso:

- il file PDF puo essere processato via OCR
- il mapping propone `ddt_number`, `ddt_date`, `total_amount`, `supplier_id`
- non salva nulla da solo

### Flusso C: creazione automatica da XML fattura

File coinvolti:

- `app/parsers/fatturapa_parser.py`
- `app/services/import_service.py`
- `app/repositories/document_repo.py`

Passi:

1. import XML FatturaPA
2. parser estrae nodi `DatiDDT`
3. se il flag `IMPORT_DDT_FROM_XML` e attivo, i DDT restano nel DTO
4. `DocumentRepository.create_from_fatturapa(...)` crea il documento
5. per ogni `DeliveryNoteDTO` crea un `DeliveryNote`

Valori tipici impostati:

- `document_id = id della fattura appena importata`
- `source = xml_expected`
- `status = unmatched`
- `import_source = import_source della fattura`
- nessun file PDF
- nessuna riga DDT

## 7. Route Flask/web esistenti per DDT

File: `app/web/routes_delivery_notes.py`

Route:

- `GET /delivery-notes/`
  - elenco DDT
- `POST /delivery-notes/`
  - creazione nuovo DDT da form
- `POST /delivery-notes/ocr`
  - OCR raw text
- `POST /delivery-notes/ocr-map`
  - OCR + mapping campi DDT
- `GET /delivery-notes/<delivery_note_id>/file`
  - apertura file salvato
- `GET|POST /delivery-notes/<delivery_note_id>`
  - dettaglio, update header, update righe, upload PDF, delete
- `GET|POST /delivery-notes/<delivery_note_id>/match-document`
  - abbina una fattura/documento a un DDT

File: `app/web/routes_documents.py`

Punti DDT lato documento:

- nella review documento esiste action `match_ddt`
- esiste `GET|POST /documents/<document_id>/match-ddt`
- nel dettaglio documento vengono caricati i DDT gia collegati

## 8. Template Jinja usati

### `app/templates/delivery_notes/list.html`

Funzioni:

- elenco DDT
- filtri per ricerca, fornitore, intestatario
- tab "Nuovo DDT"
- upload PDF
- form campi header
- anteprima PDF
- OCR opzionale

### `app/templates/delivery_notes/detail.html`

Funzioni:

- visualizzazione dati DDT
- modifica header
- modifica stato
- upload/replace PDF
- CRUD righe DDT
- delete DDT
- accesso al matching fattura

### `app/templates/delivery_notes/match_document.html`

Funzioni:

- scelta documento candidato
- stato match `matched` o `linked`

### `app/templates/documents/match_delivery_notes.html`

Funzioni:

- da un documento si puo scegliere un DDT candidato
- stati possibili nel form: `matched`, `linked`, `unmatched`

## 9. Service e repository coinvolti

### Service principali

#### `app/services/delivery_note_service.py`

Espone:

- `list_delivery_notes(...)`
- `get_delivery_note(...)`
- `get_delivery_note_with_lines(...)`
- `list_delivery_notes_by_document(...)`
- `create_delivery_note(...)`
- `upsert_delivery_note_lines(...)`
- `find_delivery_note_candidates(...)`
- `link_delivery_note_to_document(...)`
- `get_delivery_note_file_path(...)`
- `attach_delivery_note_file(...)`
- `update_delivery_note(...)`
- `delete_delivery_note(...)`

Osservazioni:

- `create_delivery_note(...)` oggi e pensato per upload PDF manuale
- richiede `file` obbligatorio
- imposta `import_source = manual_upload`

#### `app/services/import_service.py`

Rilevanza:

- legge il setting `IMPORT_DDT_FROM_XML`
- puo disattivare la generazione dei DDT attesi da XML

#### `app/services/scan_service.py`

Rilevanza:

- salva fisicamente i PDF DDT

#### `app/services/settings_service.py`

Rilevanza:

- determina path storage DDT e archivio DDT

### Repository principali

#### `app/repositories/delivery_note_repo.py`

Espone:

- `get_by_id`
- `list_for_ui`
- `find_candidates_for_match`
- `list_by_document`

Osservazioni:

- ricerca UI per numero o file name
- matching basato soprattutto su `supplier_id`
- numero/data sono opzionali nel matching

#### `app/repositories/delivery_note_line_repo.py`

Espone:

- `list_by_delivery_note`
- `get_by_id`

#### `app/repositories/document_repo.py`

Rilevanza:

- durante import FatturaPA crea i DDT attesi tramite `_create_expected_delivery_note(...)`

## 10. Endpoint API gia esistenti

Esistono solo:

- `POST /api/documents/<document_id>/status`
- `POST /api/documents/lines/<line_id>/category`

Non esiste alcun endpoint API dedicato ai DDT.

Criticita:

- le API correnti non mostrano un controllo di autenticazione applicativa
- non c'e middleware auth reale, solo stub

## 11. Come vengono salvati file, scansioni e allegati

### DDT PDF

Salvataggio tramite:

- `app/services/scan_service.py`
- `store_delivery_note_file(...)`

Comportamento:

- salvataggio in cartella `storage/ddt/<anno>/`
- copia archivio in `storage/ddt/Archivio/DDT/<anno>/`
- nel DB viene salvato il path relativo, non quello assoluto

Configurazione path:

- `settings_service.get_delivery_note_storage_path()`
- `settings_service.get_ddt_archive_path(year)`

### Allegati

Per i DDT non esiste una tabella allegati dedicata. Il file e rappresentato da:

- `file_path`
- `file_name`

## 12. Campi obbligatori

### Creazione manuale DDT

Richiesti dal service:

- `supplier_id`
- `ddt_number`
- `ddt_date`
- `file`

Opzionali:

- `legal_entity_id`
- `total_amount`
- `status`
- `source`

### Righe DDT

Perche una riga venga accettata in `upsert_delivery_note_lines(...)` servono:

- `line_number`
- `description`

Gli altri campi sono opzionali.

### DDT da XML

Perche il parser costruisca un `DeliveryNoteDTO` servono:

- `NumeroDDT`
- `DataDDT`

## 13. Stati previsti per i DDT

Stati documentati e usati in UI:

- `unmatched`
- `matched`
- `missing`
- `linked`
- `ignored`

Significato pratico:

- `unmatched`: DDT presente ma non abbinato
- `matched`: abbinato come match principale
- `linked`: collegato ma semanticamente meno forte
- `missing`: previsto ma non reperito
- `ignored`: escluso dalla lavorazione

## 14. Collegamento DDT <-> fatture/documenti

Si, il collegamento esiste gia.

Struttura:

- `delivery_notes.document_id -> documents.id`

Funzioni usate:

- `link_delivery_note_to_document(...)`
- `list_delivery_notes_by_document(...)`
- `find_delivery_note_candidates(...)`

Punti UI:

- dettaglio DDT -> abbina fattura
- review documento -> abbina DDT
- dettaglio documento -> elenco DDT collegati

Nota:

- tecnicamente il collegamento punta al supertipo `Document`, non solo a fatture XML

## 15. Validazione e deduplicazione gia presenti

### Validazioni esistenti

- obbligatorieta numero/data/file nel flusso manuale
- esistenza fornitore
- esistenza intestatario se valorizzato
- PDF richiesto nella UI

### Deduplicazione esistente

#### DDT da XML

Nel parser FatturaPA i `DatiDDT` duplicati nello stesso documento vengono deduplicati per:

- `ddt_number`
- `ddt_date`

#### Duplicazione in creazione DDT manuale/API

Non emerge un controllo di unicita o un idempotency check nel service `create_delivery_note(...)`.

Questo significa che retry o submit ripetuti possono generare doppioni.

## 16. Campi utili per distinguere la provenienza

### Gia presenti e utili

- `source`
- `import_source`

### Uso attuale

- `source` distingue il macro-canale logico
- `import_source` conserva un dettaglio libero di provenienza

### Vincolo importante

La documentazione DB dichiara valori chiusi per `source`:

- `xml_expected`
- `pdf_import`
- `manual`

Quindi, per minimizzare rischio DB, conviene:

- NON introdurre subito un nuovo valore `source = api_fitofarmaci`
- usare `source = manual`
- usare `import_source = GestionaleFitofarmaci:<external_id>`

## 17. Gap rispetto al nuovo flusso "DDT ricevuto da GestionaleFitofarmaci"

1. non esiste un endpoint DDT API
2. non esiste auth reale per chiamate machine-to-machine
3. il service attuale di creazione richiede sempre il file
4. non esiste idempotenza lato DDT
5. non esiste un campo dedicato `external_id`
6. non esiste validazione specifica della provenienza esterna
7. il matching automatico post-creazione non e previsto

## 18. Proposta di endpoint interno

### Endpoint consigliato

`POST /api/internal/delivery-notes`

### Posizionamento consigliato

Nuovo blueprint:

- `app/api/api_delivery_notes.py`

Da registrare in:

- `app/api/__init__.py`
- `app/__init__.py`

### Sicurezza consigliata

Autenticazione obbligatoria via header:

- `Authorization: Bearer <token>`

oppure:

- `X-Internal-API-Key: <token>`

Validazione token:

- da env
- oppure da `AppSetting`

### Comportamento v1 consigliato

- crea un DDT standalone
- `document_id = null`
- `status = unmatched`
- `source = manual`
- `import_source = GestionaleFitofarmaci:<external_id>`
- righe opzionali
- file PDF opzionale ma supportato

### Risposte consigliate

- `201 Created` se nuovo DDT
- `200 OK` se replay idempotente
- `400 Bad Request` se payload non valido
- `401 Unauthorized` se token mancante/errato
- `404 Not Found` se `supplier_id` o `legal_entity_id` non validi
- `409 Conflict` solo se si preferisce non gestire idempotenza morbida

## 19. Proposta di payload

### Variante JSON

```json
{
  "supplier_id": 123,
  "legal_entity_id": 4,
  "ddt_number": "DDT-4587",
  "ddt_date": "2026-05-25",
  "total_amount": "1250.50",
  "status": "unmatched",
  "external_id": "fito-2026-0004587",
  "lines": [
    {
      "line_number": 1,
      "description": "Prodotto fitosanitario X",
      "item_code": "FITO-X",
      "quantity": "10.0000",
      "uom": "pz",
      "amount": "500.00",
      "notes": "lotto 123"
    }
  ]
}
```

### Variante multipart

Campi:

- `payload`: JSON serializzato
- `file`: PDF DDT opzionale

### Campi minimi consigliati per v1

- `supplier_id`
- `ddt_number`
- `ddt_date`
- `external_id`

### Scelta consigliata per il fornitore

Per la prima versione e meglio ricevere `supplier_id` interno gia risolto.

Motivo:

- riduce ambiguita
- evita lookup complessi per partita IVA o ragione sociale
- minimizza il codice nuovo

## 20. Proposta di logica di idempotenza

Dato che non esiste un campo DB dedicato per `external_id`, la soluzione minima senza migrazione e:

- salvare `import_source = GestionaleFitofarmaci:<external_id>`
- prima di creare, cercare un DDT con:
  - stesso `supplier_id`
  - stesso `ddt_number`
  - stessa `ddt_date`
  - stesso `import_source`

Se trovato:

- restituire `200`
- `created = false`
- `duplicate = true`

Se si vuole piu robustezza futura:

- introdurre piu avanti una colonna esplicita `external_id`
- o una tabella di import log dedicata ai DDT

## 21. Rischi tecnici

### Sicurezza

Le API attuali non sono protette da auth reale. Esporre una route interna senza token sarebbe un rischio diretto.

### Duplicati

Senza idempotenza, retry HTTP del gestionale esterno possono creare DDT doppi.

### Vincoli DB su `source`

Se il DB ha davvero un check constraint coerente con la doc, aggiungere un nuovo valore `source` richiede migrazione.

### File handling

Il service corrente e centrato su upload manuale. Per API bisogna chiarire bene:

- PDF obbligatorio o no
- tipo di file accettato
- dimensione massima

### Coerenza con matching

I DDT importati da GestionaleFitofarmaci entreranno probabilmente come `unmatched`. Va valutato se in futuro serva un auto-match su fatture.

### Collegamento a documenti

Il legame a `documents` esiste gia, ma il nuovo flusso probabilmente nascera prima della fattura. Questo e compatibile con `document_id = null`.

## 22. Modifiche minime consigliate

Ordine consigliato:

1. aggiungere helper auth per API interne a token
2. creare `app/api/api_delivery_notes.py`
3. registrare il nuovo blueprint in `app/api/__init__.py` e `app/__init__.py`
4. aggiungere nel service una funzione dedicata tipo `create_delivery_note_from_external(...)`
5. riusare la logica esistente di validazione fornitore/intestatario
6. rendere il file opzionale nella nuova funzione service
7. supportare creazione righe DDT in un unico submit
8. implementare idempotenza minima con `import_source`
9. restituire payload API con `delivery_note_id`, `created`, `duplicate`, `status`
10. solo in una fase successiva valutare:
   - auto-match a fattura
   - lookup fornitore per partita IVA
   - colonna dedicata `external_id`

## 23. Raccomandazione finale

Per partire in modo rapido e a basso rischio:

- non toccare schema DB
- non introdurre nuovi valori `source`
- usare `source = manual`
- usare `import_source` per tracciare `GestionaleFitofarmaci`
- introdurre endpoint interno protetto a token
- accettare JSON o multipart
- salvare facoltativamente anche le righe DDT

Questa e la strada piu corta che resta coerente con l'architettura gia presente.
