# FITOFARMACI_INTEGRATION_SOURCE

## 1. Panoramica

Il futuro `GestionaleFitofarmaci` può leggere dal database del Gestionale Acquisti soprattutto i dati storici delle righe documento importate da FatturaPA.

Nel dominio reale della repo:

- il documento di acquisto è modellato con `Document` sulla tabella `documents`;
- le righe fattura sono modellate con `DocumentLine` sulla tabella `invoice_lines`;
- il fornitore è modellato con `Supplier` sulla tabella `suppliers`;
- il file XML/P7M di origine è tracciato principalmente in `documents.file_name` e `documents.file_path`, con supporto storico in `import_logs`.

Per il caso d'uso fitofarmaci, i dati più utili sono:

- identificativi tecnici della sorgente: `documents.id`, `invoice_lines.id`, `suppliers.id`;
- metadati documento: numero, data, tipo documento, file XML di origine;
- dati di riga: descrizione, quantità, prezzo unitario, totale riga, aliquota IVA;
- indizi utili per capire se una riga può riferirsi a un fitofarmaco: descrizione testuale, categoria gestionale assegnata, eventuali codici articolo, fornitore.

Nota importante sui nomi reali:

- nella repo non esiste un modello ORM chiamato `Invoice`;
- il supertipo reale è `Document`;
- le righe sono nella tabella reale `invoice_lines`, ma il modello ORM si chiama `DocumentLine`.

## 2. Tabelle e modelli rilevanti

### 2.1 `Document`

- Nome modello: `Document`
- Nome tabella: `documents`
- File: `app/models/document.py`
- Campi principali utili a Fitofarmaci:
  - `id`
  - `document_type`
  - `supplier_id`
  - `legal_entity_id`
  - `document_number`
  - `document_date`
  - `registration_date`
  - `due_date`
  - `total_taxable_amount`
  - `total_vat_amount`
  - `total_gross_amount`
  - `doc_status`
  - `invoice_type`
  - `import_source`
  - `file_name`
  - `file_path`
  - `imported_at`
  - `created_at`
  - `updated_at`
- Relazioni utili:
  - `supplier` -> `Supplier`
  - `legal_entity` -> `LegalEntity`
  - `invoice_lines` -> `DocumentLine`
  - `vat_summaries` -> `VatSummary`
  - `import_logs` -> `ImportLog`
- Note:
  - per le fatture acquisti standard il filtro corretto è in prima battuta `documents.document_type = 'invoice'`;
  - le note di credito FatturaPA (`TD04`) vengono salvate come `document_type = 'credit_note'`;
  - `file_name` può essere suffissato con `#bodyN` se il file XML contiene più `FatturaElettronicaBody`.

### 2.2 `DocumentLine`

- Nome modello: `DocumentLine`
- Nome tabella: `invoice_lines`
- File: `app/models/document_line.py`
- Campi principali utili a Fitofarmaci:
  - `id`
  - `document_id`
  - `category_id`
  - `line_number`
  - `description`
  - `quantity`
  - `unit_of_measure`
  - `unit_price`
  - `discount_amount`
  - `discount_percent`
  - `taxable_amount`
  - `vat_rate`
  - `vat_amount`
  - `total_line_amount`
  - `sku_code`
  - `internal_code`
  - `created_at`
  - `updated_at`
- Relazioni utili:
  - `document` -> `Document`
  - `category` -> `Category`
- Note:
  - è la tabella centrale per l'estrazione dei prodotti acquistati;
  - la descrizione riga viene alimentata dal parsing `DettaglioLinee/Descrizione`;
  - alcuni campi esistono a schema ma non risultano salvati dall'attuale repository di import, vedi sezione rischi.

### 2.3 `Supplier`

- Nome modello: `Supplier`
- Nome tabella: `suppliers`
- File: `app/models/supplier.py`
- Campi principali:
  - `id`
  - `name`
  - `vat_number`
  - `fiscal_code`
  - `sdi_code`
  - `pec_email`
  - `iban`
  - `email`
  - `phone`
  - `address`
  - `postal_code`
  - `city`
  - `province`
  - `country`
  - `is_active`
- Relazioni utili:
  - `documents` tramite backref da `Document.supplier`
- Note:
  - il collegamento documento -> fornitore passa sempre da `documents.supplier_id`;
  - per Fitofarmaci l'ID interno `suppliers.id` è il riferimento stabile da salvare.

### 2.4 `LegalEntity`

- Nome modello: `LegalEntity`
- Nome tabella: `legal_entities`
- File: `app/models/legal_entity.py`
- Campi principali:
  - `id`
  - `name`
  - `vat_number`
  - `fiscal_code`
  - `address`
  - `city`
  - `country`
  - `is_active`
- Relazioni utili:
  - `documents` tramite backref da `Document.legal_entity`
- Note:
  - non è indispensabile per la prima integrazione Fitofarmaci;
  - è utile se il deposito o il listino dovranno distinguere più intestatari aziendali.

### 2.5 `ImportLog`

- Nome modello: `ImportLog`
- Nome tabella: `import_logs`
- File: `app/models/import_log.py`
- Campi principali:
  - `id`
  - `file_name`
  - `file_hash`
  - `import_source`
  - `status`
  - `message`
  - `document_id`
  - `created_at`
- Relazioni utili:
  - `document` -> `Document`
- Note:
  - è utile come tabella di supporto per audit dell'origine XML;
  - non è la sorgente primaria del dato documento, ma può essere usata per recuperare il nome file se `documents.file_name` non basta;
  - per i normali import con successo viene scritto un record `status='success'` collegato al documento.

### 2.6 `Category`

- Nome modello: `Category`
- Nome tabella: `categories`
- File: `app/models/category.py`
- Campi principali:
  - `id`
  - `name`
  - `description`
  - `vat_rate`
  - `is_active`
- Relazioni utili:
  - `invoice_lines` -> `DocumentLine`
- Note:
  - la categoria è una classificazione gestionale interna, non un dato nativo FatturaPA;
  - può essere utile come indizio debole per riconoscere righe di fitofarmaci, ma è opzionale e assegnata manualmente.

### 2.7 `VatSummary`

- Nome modello: `VatSummary`
- Nome tabella: `vat_summaries`
- File: `app/models/vat_summary.py`
- Campi principali:
  - `id`
  - `document_id`
  - `vat_rate`
  - `taxable_amount`
  - `vat_amount`
  - `vat_nature`
- Relazioni utili:
  - `document` -> `Document`
- Note:
  - non serve per estrarre la singola riga prodotto;
  - è utile se in futuro si vuole verificare la coerenza IVA a livello documento o leggere la `vat_nature`, che non esiste su `invoice_lines`.

## 3. Percorso dati fattura -> righe -> fornitore

Il collegamento reale è questo:

1. La riga fattura sta in `invoice_lines`.
2. `invoice_lines.document_id` punta a `documents.id`.
3. Il documento contiene `document_number` e `document_date`.
4. Il documento contiene `supplier_id`.
5. `documents.supplier_id` punta a `suppliers.id`.
6. Il nome fornitore sta in `suppliers.name`.

Join logico minimo:

```text
invoice_lines.document_id -> documents.id
documents.supplier_id -> suppliers.id
```

Quindi:

- riga fattura: `invoice_lines`
- documento origine: `documents`
- fornitore: `suppliers`
- data documento: `documents.document_date`
- numero documento: `documents.document_number`

Campi di supporto aggiuntivi:

- file XML/P7M origine:
  - principalmente `documents.file_name`
  - percorso relativo archiviato in `documents.file_path`
  - audit secondario in `import_logs.file_name` tramite `import_logs.document_id`
- intestatario interno:
  - `documents.legal_entity_id` -> `legal_entities.id`

Origine applicativa dei dati:

- il parser FatturaPA legge `DettaglioLinee` e costruisce DTO con `description`, `quantity`, `unit_of_measure`, `unit_price`, `total_line_amount`, `vat_rate`;
- il repository `app/repositories/document_repo.py` crea poi `Document` e `DocumentLine` durante l'import.

## 4. Campi disponibili per estrazione fitofarmaci

| Dato necessario | Campo/modello nel gestionale acquisti | Note |
|---|---|---|
| id documento | `documents.id` (`Document.id`) | Identificativo tecnico stabile da salvare nel DB Fitofarmaci come riferimento alla sorgente. |
| numero documento | `documents.document_number` (`Document.document_number`) | Numero documento importato da FatturaPA. |
| data documento | `documents.document_date` (`Document.document_date`) | Data documento di origine. |
| id riga fattura | `invoice_lines.id` (`DocumentLine.id`) | Identificativo tecnico stabile della riga. |
| descrizione riga | `invoice_lines.description` (`DocumentLine.description`) | Campo principale per riconoscere il prodotto/fitofarmaco. |
| quantità | `invoice_lines.quantity` (`DocumentLine.quantity`) | Può essere `NULL` se la quantità non è presente o non viene valorizzata nell'origine. |
| unità di misura | `invoice_lines.unit_of_measure` (`DocumentLine.unit_of_measure`) | Il campo esiste a schema, ma l'attuale import repository non lo salva nelle righe create: nei dati storici può essere spesso `NULL`. |
| prezzo unitario | `invoice_lines.unit_price` (`DocumentLine.unit_price`) | Salvato come numerico per riga. |
| prezzo totale | `invoice_lines.total_line_amount` (`DocumentLine.total_line_amount`) | È il candidato più diretto per il totale riga. |
| aliquota IVA, se disponibile | `invoice_lines.vat_rate` (`DocumentLine.vat_rate`) | Disponibile per riga. La `vat_nature` non è sulla riga ma solo in `vat_summaries`. |
| id fornitore | `documents.supplier_id` (`Document.supplier_id`) | FK verso `suppliers.id`. |
| nome fornitore | `suppliers.name` (`Supplier.name`) | Ottenuto via join con `documents.supplier_id`. |
| file XML origine, se disponibile | `documents.file_name` oppure `import_logs.file_name` | `documents.file_name` è la sorgente primaria. Può includere suffisso `#bodyN` per file multi-body. |

Campi aggiuntivi potenzialmente utili per capire se una riga può riferirsi a un fitofarmaco:

- `invoice_lines.category_id` e `categories.name`
  - utile solo se la riga è stata classificata manualmente nel Gestionale Acquisti;
- `invoice_lines.sku_code`
  - il parser legacy prova a estrarlo da `CodiceArticolo/CodiceValore`;
  - però l'attuale repository di import non lo salva nella `DocumentLine` creata;
- `invoice_lines.internal_code`
  - esiste a schema ma non risulta popolato dall'import attuale;
- `documents.document_type`
  - permette di escludere `credit_note` nella prima fase;
- `suppliers.id` e `suppliers.name`
  - molto utili per whitelist/blacklist di fornitori tipicamente fitosanitari.

## 5. Query SQL read-only proposta

### Query iniziale consigliata

Questa query usa solo letture e restituisce il set base utile al futuro `GestionaleFitofarmaci`.

```sql
SELECT
    d.id AS purchase_document_id,
    l.id AS purchase_line_id,
    d.document_number,
    d.document_date,
    d.supplier_id AS supplier_id,
    s.name AS supplier_name,
    l.description AS line_description,
    l.quantity,
    l.unit_of_measure AS unit_of_measure,
    l.unit_price,
    l.total_line_amount AS line_total,
    l.vat_rate,
    COALESCE(d.file_name, il.file_name) AS source_file_name
FROM invoice_lines AS l
JOIN documents AS d
    ON d.id = l.document_id
LEFT JOIN suppliers AS s
    ON s.id = d.supplier_id
LEFT JOIN (
    SELECT
        document_id,
        MAX(id) AS last_import_log_id
    FROM import_logs
    WHERE document_id IS NOT NULL
    GROUP BY document_id
) AS il_last
    ON il_last.document_id = d.id
LEFT JOIN import_logs AS il
    ON il.id = il_last.last_import_log_id
WHERE d.document_type = 'invoice'
ORDER BY
    d.document_date DESC,
    d.id DESC,
    COALESCE(l.line_number, l.id) ASC;
```

### Note sulla query

- `purchase_document_id` -> `documents.id`
- `purchase_line_id` -> `invoice_lines.id`
- `source_file_name` usa `COALESCE(documents.file_name, import_logs.file_name)`
- il filtro iniziale `d.document_type = 'invoice'` esclude le note di credito
- se in futuro si vorranno importare anche rettifiche/reso, si può passare a:

```sql
WHERE d.document_type IN ('invoice', 'credit_note')
```

### Query estesa con campi utili alla classificazione

Per una seconda fase può essere utile includere anche categoria, intestatario e codici riga:

```sql
SELECT
    d.id AS purchase_document_id,
    l.id AS purchase_line_id,
    d.document_number,
    d.document_date,
    d.supplier_id AS supplier_id,
    s.name AS supplier_name,
    d.legal_entity_id,
    le.name AS legal_entity_name,
    l.line_number,
    l.description AS line_description,
    l.quantity,
    l.unit_of_measure,
    l.unit_price,
    l.taxable_amount,
    l.total_line_amount AS line_total,
    l.vat_rate,
    l.category_id,
    c.name AS category_name,
    l.sku_code,
    l.internal_code,
    d.file_name AS source_file_name,
    d.file_path AS source_file_path
FROM invoice_lines AS l
JOIN documents AS d
    ON d.id = l.document_id
LEFT JOIN suppliers AS s
    ON s.id = d.supplier_id
LEFT JOIN legal_entities AS le
    ON le.id = d.legal_entity_id
LEFT JOIN categories AS c
    ON c.id = l.category_id
WHERE d.document_type = 'invoice';
```

### Osservazioni sui `NULL`

- `unit_of_measure` può essere `NULL` anche quando l'XML lo conteneva, perché il repository di import attuale non lo persiste nella `DocumentLine`;
- `supplier_name` non dovrebbe essere normalmente `NULL` sulle fatture importate correttamente, ma può esserlo su record placeholder o dati incompleti;
- `source_file_name` può avere suffisso `#bodyN` se l'XML originale conteneva più body;
- `sku_code` e `internal_code` possono essere `NULL` o non affidabili nei dati storici.

## 6. Strategia di sincronizzazione consigliata

### Prima fase: sincronizzazione manuale tramite bottone

Approccio consigliato:

- il `GestionaleFitofarmaci` esegue una query read-only su richiesta utente;
- legge i documenti/righe e li copia nel proprio database;
- salva sempre i riferimenti tecnici sorgente:
  - `purchase_document_id`
  - `purchase_line_id`
  - `supplier_id`
  - opzionalmente `legal_entity_id`
- usa un meccanismo di upsert nel DB Fitofarmaci basato almeno su `purchase_line_id`.

Per la prima fase questo è l'approccio più semplice e sicuro perché:

- non richiede nessun accoppiamento runtime forte tra le due app;
- non richiede scritture nel database acquisti;
- permette verifica manuale dei dati importati prima dell'uso operativo.

### Fase futura: job notturno

Approccio consigliato:

- eseguire una sincronizzazione incrementale notturna;
- usare una finestra di sicurezza e non affidarsi solo a `document_date`;
- nel DB Fitofarmaci salvare `last_sync_at` e rileggere le righe aggiornate dopo quella data.

Osservazione importante:

- il campo `documents.imported_at` esiste nel modello, ma nell'import normale non risulta valorizzato in modo affidabile;
- per questo non è il miglior candidato come watermark tecnico iniziale.

Più sicuro usare:

- `documents.updated_at`
- `invoice_lines.updated_at`
- oppure, in alternativa più semplice, una sincronizzazione per intervallo date con overlap, ad esempio ultimi 30-60 giorni, sempre in upsert.

### Fase ancora futura: sincronizzazione su evento

Approccio consigliato:

- quando il Gestionale Acquisti completa l'import di una nuova fattura, emette un evento o webhook verso `GestionaleFitofarmaci`;
- il payload minimo contiene `document_id`;
- la nuova app, ricevuto l'evento, rilegge il documento dal DB acquisti con il proprio utente read-only.

Questo approccio è il più reattivo ma anche il più accoppiato.

### Conclusione pratica

Ordine raccomandato:

1. bottone manuale con import controllato;
2. job notturno con upsert incrementale;
3. evento solo quando i flussi base saranno stabili.

## 7. Sicurezza e permessi MySQL

L'utente MySQL usato dal futuro `GestionaleFitofarmaci` dovrebbe avere solo permessi `SELECT` sulle tabelle strettamente necessarie.

Tabelle minime consigliate:

- `documents`
- `invoice_lines`
- `suppliers`
- `import_logs`

Tabelle opzionali ma utili:

- `legal_entities`
- `categories`
- `vat_summaries`

Permessi da NON concedere:

- `INSERT`
- `UPDATE`
- `DELETE`
- `ALTER`
- `CREATE`
- `DROP`
- `INDEX`
- `TRIGGER`
- `EXECUTE`
- `REFERENCES`

Esempio di grant minimale:

```sql
CREATE USER 'fitofarmaci_ro'@'app_host' IDENTIFIED BY 'strong_password_here';

GRANT SELECT ON gestionale_acquisti.documents TO 'fitofarmaci_ro'@'app_host';
GRANT SELECT ON gestionale_acquisti.invoice_lines TO 'fitofarmaci_ro'@'app_host';
GRANT SELECT ON gestionale_acquisti.suppliers TO 'fitofarmaci_ro'@'app_host';
GRANT SELECT ON gestionale_acquisti.import_logs TO 'fitofarmaci_ro'@'app_host';

GRANT SELECT ON gestionale_acquisti.legal_entities TO 'fitofarmaci_ro'@'app_host';
GRANT SELECT ON gestionale_acquisti.categories TO 'fitofarmaci_ro'@'app_host';
GRANT SELECT ON gestionale_acquisti.vat_summaries TO 'fitofarmaci_ro'@'app_host';

FLUSH PRIVILEGES;
```

Raccomandazioni operative:

- limitare l'host al container o subnet reale del nuovo servizio;
- non riutilizzare l'utente applicativo del Gestionale Acquisti;
- separare le credenziali per ambiente `dev`, `staging`, `prod`;
- preferire una vista SQL dedicata in futuro, se si vorrà restringere ancora di più l'esposizione.

## 8. Rischi e ambiguità

### 8.1 Campi presenti a schema ma non affidabili nei dati storici

Sono emersi campi che esistono nel modello `DocumentLine`, ma l'attuale metodo `DocumentRepository._create_line()` non li valorizza durante l'import FatturaPA:

- `unit_of_measure`
- `discount_amount`
- `discount_percent`
- `sku_code`
- `internal_code`

Quindi:

- questi campi vanno considerati disponibili a schema;
- ma non vanno considerati affidabili nei dati storici già importati.

### 8.2 Unità di misura non normalizzate

Anche se il campo fosse valorizzato, l'origine FatturaPA usa testo libero come `UnitaMisura`.

Esempi tipici possibili:

- `KG`
- `kg`
- `L`
- `LT`
- `PZ`
- stringhe fornitore-specifiche

Quindi il nuovo progetto dovrà prevedere una normalizzazione interna delle unità di misura.

### 8.3 Righe fattura difficili da riconoscere

Il riconoscimento del fitofarmaco non può basarsi su un solo campo certo.

Il dato più utile è:

- `invoice_lines.description`

Ma le descrizioni possono essere:

- generiche;
- abbreviate;
- con nomi commerciali diversi;
- con confezioni o dosi incluse nel testo;
- scritte in modo diverso tra fornitori o tra fatture dello stesso fornitore.

### 8.4 Prodotti con descrizioni leggermente diverse

Lo stesso prodotto può comparire con:

- nome commerciale completo;
- nome abbreviato;
- variante con quantità/confezione nel testo;
- refusi o punteggiatura diversa.

Per questo il nuovo progetto dovrebbe:

- salvare la descrizione originale;
- affiancare una tabella propria di normalizzazione/prodotto canonico;
- evitare di usare subito matching troppo automatici nella prima fase.

### 8.5 Prezzi unitari e totali

Possibili criticità:

- `quantity` può essere `NULL`;
- `unit_of_measure` può essere `NULL`;
- `unit_price` e `total_line_amount` sono per riga, ma il significato commerciale può dipendere da sconti o confezioni descritte nel testo;
- `taxable_amount` e `total_line_amount` possono coincidere o differire a seconda del parser/percorso dati;
- le note di credito hanno importi con segno invertito dal repository di import.

Per la prima fase è meglio usare come valore economico principale:

- `invoice_lines.total_line_amount` per il totale riga;
- `invoice_lines.unit_price` solo come dato accessorio;
- `documents.document_type` per escludere inizialmente `credit_note`.

### 8.6 Watermark di sincronizzazione

Il campo `documents.imported_at` esiste, ma l'import normale non lo valorizza in modo consistente nel percorso osservato.

Quindi:

- non è consigliato usarlo come watermark primario per la sincronizzazione;
- sono più sicuri `updated_at`, oppure un upsert periodico su finestra temporale.

### 8.7 Categoria come indizio, non come verità

`invoice_lines.category_id` può essere utile, ma:

- è opzionale;
- dipende da classificazione manuale;
- può non essere stata assegnata a tutte le righe.

Va quindi trattata come segnale secondario, non come criterio esclusivo.

## 9. Raccomandazioni per il nuovo progetto

### Dati da leggere

Per la prima versione del `GestionaleFitofarmaci` leggere almeno:

- da `documents`:
  - `id`
  - `document_type`
  - `document_number`
  - `document_date`
  - `supplier_id`
  - `legal_entity_id`
  - `file_name`
  - `file_path`
  - `updated_at`
- da `invoice_lines`:
  - `id`
  - `document_id`
  - `line_number`
  - `description`
  - `quantity`
  - `unit_of_measure`
  - `unit_price`
  - `taxable_amount`
  - `total_line_amount`
  - `vat_rate`
  - `category_id`
  - `updated_at`
- da `suppliers`:
  - `id`
  - `name`
  - `vat_number`
  - `fiscal_code`
- opzionalmente da `categories`:
  - `id`
  - `name`
- opzionalmente da `import_logs`:
  - `file_name`
  - `file_hash`
  - `created_at`

### Dati da copiare nel nuovo DB

Nel DB del `GestionaleFitofarmaci` conviene copiare una snapshot autonoma dei dati necessari, non leggere live il DB acquisti a ogni schermata.

Campi consigliati da salvare:

- `purchase_document_id`
- `purchase_line_id`
- `supplier_id`
- `legal_entity_id`
- `document_number`
- `document_date`
- `supplier_name`
- `line_number`
- `line_description_original`
- `quantity_original`
- `unit_of_measure_original`
- `unit_price_original`
- `line_total_original`
- `vat_rate`
- `source_file_name`
- `source_file_path`
- `category_id`
- `category_name`
- timestamp di sincronizzazione locale

### Riferimenti da salvare sempre

I riferimenti minimi da conservare per tracciabilità sono:

- `purchase_document_id`
- `purchase_line_id`
- `supplier_id`

Sono i riferimenti migliori per:

- deduplicare;
- fare upsert;
- risalire al documento originale nel Gestionale Acquisti.

### Automatismi da evitare nella prima fase

Nella prima fase è meglio evitare:

- classificazione automatica definitiva del prodotto basata solo sulla descrizione;
- aggiornamenti automatici aggressivi del listino senza revisione;
- sincronizzazione event-driven immediata;
- dipendenza da campi non affidabili come `unit_of_measure`, `sku_code`, `internal_code`;
- inclusione automatica delle `credit_note` nel calcolo prezzi/giacenze.

### Approccio pratico consigliato

Per partire in modo solido:

1. leggere solo `documents.document_type = 'invoice'`;
2. sincronizzare con bottone manuale;
3. salvare snapshot locale delle righe;
4. far classificare o confermare all'utente le righe candidate fitofarmaci;
5. introdurre solo dopo una normalizzazione prodotti, unità di misura e fornitori.

## Fonti verificate nella repo

Analisi basata su:

- `docs/00_INDEX.md`
- `docs/database.md`
- `docs/architecture.md`
- `docs/fatturapa/PARSING_REFERENCE.md`
- `app/models/document.py`
- `app/models/document_line.py`
- `app/models/supplier.py`
- `app/models/legal_entity.py`
- `app/models/import_log.py`
- `app/models/category.py`
- `app/models/vat_summary.py`
- `app/repositories/document_repo.py`
- `app/repositories/document_line_repo.py`
- `app/repositories/import_log_repo.py`
- `app/repositories/supplier_repo.py`
- `app/services/import_service.py`
- `app/services/document_service.py`
- `app/services/unit_of_work.py`
- `app/parsers/fatturapa_parser.py`
- `app/parsers/fatturapa_parser_v2.py`
