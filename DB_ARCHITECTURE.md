# DB_ARCHITECTURE.md

Architettura del database – Gestionale Acquisti  
Versione: v3 (supertipo documents + Single Table Inheritance)

---

## 1. Obiettivi di design

Il database modella l'intero flusso del ciclo passivo per **tutti i tipi di documento economico**:

1. **Ingresso documenti** (XML FatturaPA, PDF F24, PDF assicurazioni, ecc. → Documents).
2. **Revisione e conferma** (stato documento, intestazione, categorie).
3. **Gestione copia fisica** (scanner, file system).
4. **Pianificazione e registrazione pagamenti** (scadenze + collegamento ai PDF bancari).
5. **Gestione DDT / bolle** (PDF DDT + riferimenti su fatture differite).
6. **Logging e configurazione applicativa** (import, impostazioni, note).

Principi:

- **Fonte unica della verità** dove possibile.
- **Supertipo unificato** (`documents`) per tutti i documenti economici.
- **Single Table Inheritance** per evitare UNION massive.
- **Relazioni esplicite**: niente colonne "magiche", chiavi esterne chiare.
- **Estendibilità** per nuovi tipi di documento senza refactor strutturale.

---

## 2. Architettura Generale: Single Table Inheritance

### Pattern Scelto
```
documents (supertipo)
  ├─ Colonne comuni a TUTTI i documenti
  ├─ document_type ENUM per discriminare il tipo
  └─ Colonne nullable specifiche per ogni tipo
  
Tabelle specializzate (dettagli):
  ├─ invoice_lines (righe fatture)
  ├─ vat_summaries (riepiloghi IVA fatture)
  └─ rent_contracts (contratti affitto)
```

**Vantaggi:**
- Query cross-document semplici: `SELECT * FROM documents WHERE supplier_id = X`
- FK unificati: `payments.document_id` → qualsiasi tipo documento
- Estensione immediata: aggiungi nuovo `document_type` + colonne specifiche
- Nessun UNION per report aggregati

**Trade-off accettati:**
- Molte colonne NULL (colonne specifiche di un tipo sono NULL per altri tipi)
- Tabella "larga" (~45 colonne), ma gestibile per < 20 tipi documento

---

## 3. Entità principali e relazioni

### 3.1. Anagrafiche: Fornitori e Intestatari

#### `suppliers`
Rappresenta il fornitore (controparte esterna).

Campi principali:

- `id`
- `name`
- `vat_number` (UNIQUE)
- `fiscal_code` (rinominato da `tax_code` per uniformità)
- dati di contatto (email, PEC, indirizzo, ecc.)
- `is_active`
- `created_at`, `updated_at`

Uso:

- Relazionato a `documents.supplier_id`
- Relazionato a `payment_documents.supplier_id`
- Relazionato a `delivery_notes.supplier_id`

#### `legal_entities`
Rappresenta l'intestatario "interno" (le varie società / partite IVA dell'azienda).

Campi principali:

- `id`
- `name`
- `vat_number` (UNIQUE)
- `fiscal_code`
- dati fiscali e indirizzo
- `is_active`
- `created_at`, `updated_at`

**Nota:** La colonna `tax_code` è stata **rimossa** (era sempre NULL).

Uso:

- Relazionato a `documents.legal_entity_id`
- Relazionato a `delivery_notes.legal_entity_id`

---

### 3.2. Documenti (SUPERTIPO)

#### `documents`

**Tabella centrale del sistema.** Rappresenta TUTTI i documenti economici di acquisto.

##### Colonne Comuni (tutti i document_type)

**Identificazione:**
- `id` (PK)
- `document_type` VARCHAR(32) NOT NULL
  - Valori: `'invoice'`, `'f24'`, `'insurance'`, `'mav'`, `'cbill'`, `'receipt'`, `'rent'`, `'tax'`, `'other'`

**Anagrafiche:**
- `supplier_id` (FK → suppliers) NOT NULL
- `legal_entity_id` (FK → legal_entities) NOT NULL

**Dati Documento:**
- `document_number` VARCHAR(64)
- `document_date` DATE
- `due_date` DATE (riferimento, la gestione vera è in `payments`)
- `registration_date` DATE

**Importi:**
- `total_taxable_amount` DECIMAL(15,2) (imponibile, per documenti con IVA)
- `total_vat_amount` DECIMAL(15,2) (IVA)
- `total_gross_amount` DECIMAL(15,2) NOT NULL (totale)

**Stato:**
- `doc_status` VARCHAR(32) NOT NULL DEFAULT 'imported'
  - Valori: `'imported'`, `'verified'`, `'rejected'`, `'cancelled'`, `'archived'`

**Import:**
- `import_source` VARCHAR(255)
- `file_name` VARCHAR(255)
- `file_path` VARCHAR(255)
- `imported_at` DATETIME

**Copia Fisica:**
- `physical_copy_status` VARCHAR(32) NOT NULL DEFAULT 'missing'
  - Valori: `'missing'`, `'requested'`, `'received'`, `'uploaded'`, `'not_required'`
- `physical_copy_requested_at` DATETIME
- `physical_copy_received_at` DATETIME

**Audit:**
- `created_at` DATETIME NOT NULL
- `updated_at` DATETIME NOT NULL

##### Colonne Specifiche per Tipo Documento (nullable)

**FATTURE** (`document_type = 'invoice'`):
- `invoice_type` VARCHAR(16) – `'immediate'` | `'deferred'`

**F24** (`document_type = 'f24'`):
- `f24_period_from` DATE
- `f24_period_to` DATE
- `f24_tax_type` VARCHAR(64) – tipo tributo
- `f24_payment_code` VARCHAR(64) – codice tributo

**ASSICURAZIONI** (`document_type = 'insurance'`):
- `insurance_policy_number` VARCHAR(64)
- `insurance_coverage_start` DATE
- `insurance_coverage_end` DATE
- `insurance_type` VARCHAR(64) – `'vehicle'`, `'property'`, `'crop'`, `'liability'`
- `insurance_asset_description` TEXT

**AFFITTI** (`document_type = 'rent'`):
- `rent_contract_id` INT (FK → rent_contracts)
- `rent_period_month` INT (1-12)
- `rent_period_year` INT
- `rent_property_description` VARCHAR(255)

**MAV/CBILL** (`document_type = 'mav'` | `'cbill'`):
- `payment_code` VARCHAR(64) – codice avviso
- `creditor_entity` VARCHAR(255) – ente creditore

**SCONTRINI** (`document_type = 'receipt'`):
- `receipt_merchant` VARCHAR(255)
- `receipt_category` VARCHAR(64)

**TRIBUTI/TASSE** (`document_type = 'tax'`):
- `tax_type` VARCHAR(64) – `'imu'`, `'tari'`, `'tasi'`, `'canone'`
- `tax_period_year` INT
- `tax_period_description` VARCHAR(128)

##### CHECK Constraints
```sql
-- Tipo documento valido
CHECK (document_type IN ('invoice', 'f24', 'insurance', 'mav', 'cbill', 'receipt', 'rent', 'tax', 'other'))

-- Stato valido
CHECK (doc_status IN ('imported', 'verified', 'rejected', 'cancelled', 'archived'))

-- invoice_type valorizzato solo per fatture
CHECK (
  (document_type = 'invoice' AND invoice_type IN ('immediate', 'deferred'))
  OR (document_type != 'invoice' AND invoice_type IS NULL)
)

-- f24_payment_code valorizzato solo per F24
CHECK (
  (document_type = 'f24' AND f24_payment_code IS NOT NULL)
  OR (document_type != 'f24' AND f24_payment_code IS NULL)
)

-- insurance_policy_number valorizzato solo per assicurazioni
CHECK (
  (document_type = 'insurance' AND insurance_policy_number IS NOT NULL)
  OR (document_type != 'insurance' AND insurance_policy_number IS NULL)
)
```

##### Relazioni

- 1:N con `invoice_lines` (solo per document_type='invoice')
- 1:N con `vat_summaries` (solo per document_type='invoice')
- 1:N con `payments` (scadenze, per TUTTI i tipi)
- 1:N con `delivery_notes` (DDT, solo per fatture differite)
- 1:N con `notes` (note, per TUTTI i tipi)
- 1:N con `import_logs` (log, per TUTTI i tipi)

---

### 3.3. Dettagli Documenti (Tabelle Specializzate)

#### `invoice_lines`

Righe di dettaglio delle **fatture**.

Campi:

- `id`
- `document_id` (FK → documents WHERE document_type='invoice')
- `category_id` (FK → categories, opzionale)
- `line_number`
- descrizione, quantità, prezzo, sconti, ecc.
- `taxable_amount`, `vat_rate`, `vat_amount`, `total_line_amount`
- `sku_code`, `internal_code`
- `created_at`, `updated_at`

#### `vat_summaries`

Riepiloghi IVA per **fatture**.

Campi:

- `id`
- `document_id` (FK → documents WHERE document_type='invoice')
- `vat_rate`
- `taxable_amount`, `vat_amount`
- `vat_nature` (N1, N2, N3, ecc.)
- `created_at`, `updated_at`

#### `rent_contracts`

Contratti di **affitto** (generano documenti mensili in `documents` con document_type='rent').

Campi:

- `id`
- `contract_number` (UNIQUE)
- `supplier_id` (FK → suppliers, proprietario)
- `legal_entity_id` (FK → legal_entities, conduttore)
- `property_description`, `property_address`
- `monthly_amount`, `start_date`, `end_date`
- `payment_day` (giorno del mese per pagamento rata)
- `is_active`
- `notes`
- `created_at`, `updated_at`

---

### 3.4. Scadenze e Pagamenti

Questo è il "cuore" del sistema di gestione finanziaria.

#### `payments`

Tabella delle **scadenze** e dello **stato di pagamento** per **TUTTI i documenti**.

Campi principali:

- `id`
- `document_id` (FK → documents, qualsiasi tipo)
- `payment_document_id` (FK → payment_documents, se riconciliato)
- `due_date` – data scadenza della rata
- `expected_amount` – importo previsto per questa rata
- `paid_amount` – importo già pagato su questa rata
- `paid_date` – data dell'ultimo saldo
- `status` VARCHAR(32) NOT NULL DEFAULT 'unpaid'
  - Valori: `'unpaid'`, `'planned'`, `'pending'`, `'partial'`, `'paid'`, `'cancelled'`, `'overdue'`
- `payment_terms` VARCHAR(128) – condizioni pagamento (es. "30gg DFFM")
- `payment_method` VARCHAR(64) – metodo previsto
- `notes` TEXT
- `created_at`, `updated_at`

**Semantica:**

- Quando un documento viene confermato, si crea **almeno una riga** in `payments` con:
  - `due_date` = scadenza del documento (o prima rata se rateizzato)
  - `expected_amount` = totale documento (o quota se rateizzato)
  - `status = 'unpaid'` o `'planned'`
- Quando arriva un pagamento reale, la riga viene aggiornata:
  - `paid_amount`, `paid_date`, `status` (`'partial'` / `'paid'`)

**Lo scadenziario lavora sui `payments` aperti**, non direttamente sui documenti.

#### `payment_documents`

PDF di **bonifici, MAV, assegni**, ecc. importati dal sistema.

Campi:

- `id`
- `supplier_id` (FK → suppliers, opzionale ma utile)
- `file_name`, `file_path`
- `payment_type` VARCHAR(32) – `'sconosciuto'`, `'bonifico'`, `'rid'`, `'mav'`, `'cbill'`, `'assegno'`, `'contanti'`, `'carta'`, `'f24'`
- `status` VARCHAR(32) – `'pending_review'`, `'imported'`, `'reconciled'`, `'partial'`, `'ignored'`
- `uploaded_at`
- `parsed_amount`, `parsed_payment_date`, `parsed_document_number` (da OCR)
- `parse_error_message` TEXT
- `created_at`, `updated_at`

#### `payment_document_links`

Tabella ponte **M:N** tra scadenze (`payments`) e PDF bancari (`payment_documents`).

Serve per gestire:

- un bonifico che copre più scadenze
- una rata pagata con più movimenti

Campi:

- `id`
- `payment_document_id` (FK → payment_documents)
- `payment_id` (FK → payments)
- `allocated_amount` – quota del bonifico assegnata a quella scadenza
- `created_at`

---

### 3.5. DDT / Bolle

#### `delivery_notes`

Rappresenta i DDT sia **attesi da XML** (fatture differite) sia **reali importati da PDF**.

Campi:

- `id`
- `document_id` (FK → documents, solo per document_type='invoice' con invoice_type='deferred')
- `supplier_id` (FK → suppliers)
- `legal_entity_id` (FK → legal_entities)
- `ddt_number`, `ddt_date`
- `total_amount`
- `file_path`, `file_name` (se PDF)
- `source` VARCHAR(32) – `'xml_expected'`, `'pdf_import'`, `'manual'`
- `import_source`, `imported_at`
- `status` VARCHAR(32) – `'unmatched'`, `'matched'`, `'missing'`, `'linked'`, `'ignored'`
- `created_at`, `updated_at`

**Flusso operativo:**

- All'import della fattura differita:
  - per ogni DDT citato nel XML → si crea riga con `source='xml_expected'`, `status='unmatched'`

- All'import PDF delle bolle:
  - si crea riga con `source='pdf_import'`, `status='unmatched'`

- Matching automatico/manuale:
  - se atteso trova reale → `status='matched'`, `document_id` impostato
  - se atteso non trova reale → `status='missing'`

---

### 3.6. Classificazione

#### `categories`

Categorie di spesa per classificare le righe fattura.

Campi:

- `id`
- `name` (UNIQUE)
- `description`
- `is_active`
- `created_at`, `updated_at`

Relazione:

- 1:N con `invoice_lines.category_id`

#### `notes`

Note operative e commenti sui **documenti** (qualsiasi tipo).

Campi:

- `id`
- `document_id` (FK → documents, qualsiasi tipo)
- `user_id` (FK → users)
- `content` TEXT
- `created_at`

---

### 3.7. Logging e Impostazioni Applicative

#### `import_logs`

Log dei file XML/PDF importati.

Campi:

- `id`
- `document_id` (FK → documents, se l'import ha generato un documento)
- `file_name`, `file_hash`
- `import_source`
- `status` VARCHAR(32) – `'success'`, `'error'`, `'warning'`, `'duplicate'`
- `message` TEXT (dettagli errore o info)
- `created_at`

Uso:

- Audit trail degli import
- Diagnostica errori di parsing o duplicati

#### `app_settings`

Configurazioni globali modificabili a runtime.

Campi:

- `id`
- `setting_key` VARCHAR(191) (UNIQUE)
- `value` TEXT
- `description` VARCHAR(255)
- `created_at`, `updated_at`

#### `users`

Utenti dell'applicazione.

Campi:

- `id`
- `username` (UNIQUE), `full_name`, `email` (UNIQUE)
- `role` VARCHAR(32) – `'admin'`, `'user'`, `'readonly'`
- `is_active`
- `created_at`, `updated_at`

Relazioni:

- autore delle `notes`

---

## 4. Convenzioni e Principi di Design

### 4.1. Naming Unificato

Tutte le colonne comuni usano nomi **generici** per facilitare estensioni future:

- `document_date` (non `invoice_date`)
- `document_number` (non `invoice_number`)
- `doc_status` (comune a tutti i tipi)
- `total_gross_amount` (comune)

### 4.2. CHECK Constraints su Enum

Tutti i campi enum sono protetti da CHECK constraints per evitare typo:

- `documents.document_type`
- `documents.doc_status`
- `documents.invoice_type` (con vincolo condizionale)
- `payments.status`
- `delivery_notes.status` e `delivery_notes.source`
- `payment_documents.status` e `payment_documents.payment_type`
- `import_logs.status`
- `users.role`

### 4.3. UNIQUE Constraints

- `suppliers.vat_number` → UNIQUE (no duplicati P.IVA fornitori)
- `legal_entities.vat_number` → UNIQUE (no duplicati P.IVA intestatari)
- `rent_contracts.contract_number` → UNIQUE
- `categories.name` → UNIQUE
- `users.username`, `users.email` → UNIQUE
- `app_settings.setting_key` → UNIQUE

### 4.4. Fonte di Verità

#### Scadenze
- **Fonte unica:** `payments` table
- `documents.due_date` è solo **metadata di riferimento**
- Lo scadenziario legge **solo** da `payments`

#### Pagamenti Reali
- **Fonte unica:** `payment_documents` table
- Mapping M:N via `payment_document_links` quando un movimento copre più scadenze

#### Totali Fattura
- **Ridondanza accettata:** `documents.total_*` vs somma `invoice_lines` + `vat_summaries`
- Mantenuta per performance (filtri rapidi senza JOIN)
- Consistenza garantita dal livello applicativo

---

## 5. Estensione Futura: Aggiungere Nuovo Tipo Documento

Per aggiungere un nuovo tipo (es. "contratti di manutenzione"):

### Step 1: Aggiorna CHECK constraint
```sql
ALTER TABLE documents DROP CONSTRAINT chk_documents_type;
ALTER TABLE documents ADD CONSTRAINT chk_documents_type
  CHECK (document_type IN (
    'invoice', 'f24', 'insurance', 'mav', 'cbill', 
    'receipt', 'rent', 'tax', 
    'maintenance_contract',  -- NUOVO
    'other'
  ));
```

### Step 2: Aggiungi colonne specifiche (se necessario)
```sql
ALTER TABLE documents 
  ADD COLUMN maintenance_contract_number VARCHAR(64) DEFAULT NULL,
  ADD COLUMN maintenance_start_date DATE DEFAULT NULL,
  ADD COLUMN maintenance_end_date DATE DEFAULT NULL,
  ADD COLUMN maintenance_frequency VARCHAR(32) DEFAULT NULL;
```

### Step 3: Aggiungi CHECK constraint condizionale
```sql
ALTER TABLE documents ADD CONSTRAINT chk_documents_maintenance
  CHECK (
    (document_type = 'maintenance_contract' AND maintenance_contract_number IS NOT NULL)
    OR (document_type != 'maintenance_contract' AND maintenance_contract_number IS NULL)
  );
```

### Step 4: (Opzionale) Aggiungi tabella specializzata
```sql
CREATE TABLE maintenance_contract_details (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT NOT NULL,
  service_description TEXT,
  ...
  FOREIGN KEY (document_id) REFERENCES documents(id)
);
```

**Nessun refactor di `payments`, `notes`, `import_logs`, ecc. → Tutto funziona automaticamente!**

---

## 6. Query Comuni

### Dashboard: Documenti in Scadenza
```sql
SELECT 
  d.document_type,
  d.document_number,
  d.document_date,
  d.total_gross_amount,
  p.due_date,
  p.expected_amount,
  s.name AS supplier_name
FROM documents d
JOIN payments p ON p.document_id = d.id
JOIN suppliers s ON s.id = d.supplier_id
WHERE p.status IN ('unpaid', 'pending', 'partial')
  AND p.due_date <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
ORDER BY p.due_date;
```

### Estratto Conto Fornitore (Tutti i Documenti)
```sql
SELECT 
  document_type,
  document_number,
  document_date,
  total_gross_amount,
  doc_status
FROM documents
WHERE supplier_id = :supplier_id
ORDER BY document_date DESC;
```

### Scadenziario Mensile
```sql
SELECT 
  d.document_type,
  d.document_number,
  p.due_date,
  p.expected_amount,
  p.paid_amount,
  p.status
FROM payments p
JOIN documents d ON d.id = p.document_id
WHERE MONTH(p.due_date) = MONTH(CURDATE())
  AND YEAR(p.due_date) = YEAR(CURDATE())
  AND p.status != 'paid'
ORDER BY p.due_date;
```

### Report per Tipo Documento
```sql
SELECT 
  document_type,
  COUNT(*) AS num_documents,
  SUM(total_gross_amount) AS total_amount
FROM documents
WHERE YEAR(document_date) = YEAR(CURDATE())
GROUP BY document_type
ORDER BY total_amount DESC;
```

---

## 7. Diagramma Logico (Testuale)
```
suppliers (1) ──────< (N) documents
legal_entities (1) ──< (N) documents

documents (1) ──────< (N) invoice_lines (solo invoice)
documents (1) ──────< (N) vat_summaries (solo invoice)
documents (1) ──────< (N) payments (TUTTI i tipi)
documents (1) ──────< (N) delivery_notes (solo invoice deferred)
documents (1) ──────< (N) notes (TUTTI i tipi)
documents (1) ──────< (N) import_logs (TUTTI i tipi)

payments (N) ──────> (1) payment_documents (opzionale)
payment_documents (1) ──< (N) payment_document_links >──< (N) payments

suppliers (1) ──────< (N) payment_documents
suppliers (1) ──────< (N) delivery_notes
suppliers (1) ──────< (N) rent_contracts

legal_entities (1) ──< (N) delivery_notes
legal_entities (1) ──< (N) rent_contracts

categories (1) ──────< (N) invoice_lines

users (1) ───────< (N) notes
```

---

## 8. Note Finali

- Questo schema è **production-ready** per gestire fatture, F24, assicurazioni, MAV, CBILL, scontrini, affitti, tributi.
- L'estensione a nuovi tipi è **immediata** (aggiungi `document_type` + colonne nullable).
- La consistenza dei dati è garantita da **CHECK constraints** e **FK**.
- Le performance sono ottimizzate con **indici compound** sui path di query più frequenti.
- Il modello è **futureproof**: può evolvere senza refactor massivi.