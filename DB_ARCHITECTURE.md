# DB_ARCHITECTURE.md

Architettura del database – Gestionale Acquisti  
Versione: v3 (supertipo documents + Single Table Inheritance)  
Ultimo aggiornamento: 11 Dicembre 2025

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

```sql
CREATE TABLE suppliers (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  vat_number VARCHAR(32) UNIQUE,
  fiscal_code VARCHAR(32),
  sdi_code VARCHAR(16),
  pec_email VARCHAR(255),
  email VARCHAR(255),
  phone VARCHAR(64),
  address VARCHAR(255),
  postal_code VARCHAR(16),
  city VARCHAR(128),
  province VARCHAR(64),
  country VARCHAR(64),
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

**Indici:**
- `idx_suppliers_vat_unique` (UNIQUE su vat_number)
- `idx_suppliers_name` (su name)
- `idx_suppliers_created_at` (su created_at)

**Uso:**
- Relazionato a `documents.supplier_id`
- Relazionato a `payment_documents.supplier_id`
- Relazionato a `delivery_notes.supplier_id`
- Relazionato a `rent_contracts.supplier_id`

#### `legal_entities`
Rappresenta l'intestatario "interno" (le varie società / partite IVA dell'azienda).

Campi principali:

```sql
CREATE TABLE legal_entities (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  vat_number VARCHAR(32) UNIQUE,
  fiscal_code VARCHAR(32),
  sdi_code VARCHAR(16),
  address VARCHAR(255),
  postal_code VARCHAR(16),
  city VARCHAR(128),
  province VARCHAR(64),
  country VARCHAR(64),
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

**Indici:**
- `idx_legal_entities_vat_unique` (UNIQUE su vat_number)
- `idx_legal_entities_name` (su name)

**Uso:**
- Relazionato a `documents.legal_entity_id`
- Relazionato a `delivery_notes.legal_entity_id`
- Relazionato a `rent_contracts.legal_entity_id`

---

### 3.2. Documenti (SUPERTIPO)

#### `documents`

**Tabella centrale del sistema.** Rappresenta TUTTI i documenti economici di acquisto.

##### Schema Completo

```sql
CREATE TABLE documents (
  -- Identificazione
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_type VARCHAR(32) NOT NULL,
  
  -- Anagrafiche
  supplier_id INT NOT NULL,
  legal_entity_id INT NOT NULL,
  
  -- Dati Documento
  document_number VARCHAR(64),
  document_date DATE,
  due_date DATE,
  registration_date DATE,
  
  -- Importi
  total_taxable_amount DECIMAL(15,2),
  total_vat_amount DECIMAL(15,2),
  total_gross_amount DECIMAL(15,2) NOT NULL,
  
  -- Stato
  doc_status VARCHAR(32) NOT NULL DEFAULT 'imported',
  
  -- Import
  import_source VARCHAR(255),
  file_name VARCHAR(255),
  file_path VARCHAR(255),
  imported_at DATETIME,
  
  -- Copia Fisica
  physical_copy_status VARCHAR(32) NOT NULL DEFAULT 'missing',
  physical_copy_requested_at DATETIME,
  physical_copy_received_at DATETIME,
  
  -- COLONNE SPECIFICHE PER TIPO: FATTURE
  invoice_type VARCHAR(16),
  
  -- COLONNE SPECIFICHE PER TIPO: F24
  f24_period_from DATE,
  f24_period_to DATE,
  f24_tax_type VARCHAR(64),
  f24_payment_code VARCHAR(64),
  
  -- COLONNE SPECIFICHE PER TIPO: ASSICURAZIONI
  insurance_policy_number VARCHAR(64),
  insurance_coverage_start DATE,
  insurance_coverage_end DATE,
  insurance_type VARCHAR(64),
  insurance_asset_description TEXT,
  
  -- COLONNE SPECIFICHE PER TIPO: AFFITTI
  rent_contract_id INT,
  rent_period_month INT,
  rent_period_year INT,
  rent_property_description VARCHAR(255),
  
  -- COLONNE SPECIFICHE PER TIPO: MAV/CBILL
  payment_code VARCHAR(64),
  creditor_entity VARCHAR(255),
  
  -- COLONNE SPECIFICHE PER TIPO: SCONTRINI
  receipt_merchant VARCHAR(255),
  receipt_category VARCHAR(64),
  
  -- COLONNE SPECIFICHE PER TIPO: TRIBUTI/TASSE
  tax_type VARCHAR(64),
  tax_period_year INT,
  tax_period_description VARCHAR(128),
  
  -- Audit
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  -- Foreign Keys
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
  FOREIGN KEY (legal_entity_id) REFERENCES legal_entities(id),
  FOREIGN KEY (rent_contract_id) REFERENCES rent_contracts(id),
  
  -- Check Constraints
  CONSTRAINT chk_documents_type 
    CHECK (document_type IN ('invoice', 'f24', 'insurance', 'mav', 
                             'cbill', 'receipt', 'rent', 'tax', 'other')),
  
  CONSTRAINT chk_documents_status 
    CHECK (doc_status IN ('imported', 'verified', 'rejected', 
                          'cancelled', 'archived')),
  
  CONSTRAINT chk_documents_physical_copy 
    CHECK (physical_copy_status IN ('missing', 'requested', 'received', 
                                    'uploaded', 'not_required')),
  
  CONSTRAINT chk_documents_invoice_type 
    CHECK ((document_type = 'invoice' AND invoice_type IN ('immediate', 'deferred'))
           OR (document_type != 'invoice' AND invoice_type IS NULL)),
  
  CONSTRAINT chk_documents_f24_code 
    CHECK ((document_type = 'f24' AND f24_payment_code IS NOT NULL)
           OR (document_type != 'f24' AND f24_payment_code IS NULL)),
  
  CONSTRAINT chk_documents_insurance_policy 
    CHECK ((document_type = 'insurance' AND insurance_policy_number IS NOT NULL)
           OR (document_type != 'insurance' AND insurance_policy_number IS NULL)),
  
  CONSTRAINT chk_documents_rent_contract 
    CHECK ((document_type = 'rent' AND rent_contract_id IS NOT NULL)
           OR (document_type != 'rent' AND rent_contract_id IS NULL))
);
```

**Indici Implementati:**

```sql
-- Indici principali per lookup e JOIN
idx_documents_supplier (supplier_id)
idx_documents_legal_entity (legal_entity_id)
idx_documents_document_date (document_date)

-- Indici compound per query complesse
idx_documents_supplier_date (supplier_id, document_date DESC)
idx_documents_legal_entity_date (legal_entity_id, document_date DESC)
idx_documents_status_date (doc_status, document_date DESC)
idx_documents_type_date (document_type, document_date DESC)

-- Indici per filtri specifici
idx_documents_physical_copy (physical_copy_status)
idx_documents_created_at (created_at)
```

##### Descrizione Campi Principali

**Colonne Comuni (tutti i document_type):**

- `document_type` VARCHAR(32) NOT NULL
  - Valori: `'invoice'`, `'f24'`, `'insurance'`, `'mav'`, `'cbill'`, `'receipt'`, `'rent'`, `'tax'`, `'other'`
  - Discriminatore del tipo di documento

- `doc_status` VARCHAR(32) NOT NULL DEFAULT 'imported'
  - Valori: `'imported'`, `'verified'`, `'rejected'`, `'cancelled'`, `'archived'`
  - Stato del documento nel workflow

- `physical_copy_status` VARCHAR(32) NOT NULL DEFAULT 'missing'
  - Valori: `'missing'`, `'requested'`, `'received'`, `'uploaded'`, `'not_required'`
  - Stato della copia fisica cartacea

**Colonne Specifiche per Tipo:**

- **FATTURE** (`document_type = 'invoice'`):
  - `invoice_type` VARCHAR(16) – `'immediate'` | `'deferred'`

- **F24** (`document_type = 'f24'`):
  - `f24_period_from`, `f24_period_to` DATE
  - `f24_tax_type` VARCHAR(64) – tipo tributo
  - `f24_payment_code` VARCHAR(64) – codice tributo (OBBLIGATORIO)

- **ASSICURAZIONI** (`document_type = 'insurance'`):
  - `insurance_policy_number` VARCHAR(64) (OBBLIGATORIO)
  - `insurance_coverage_start`, `insurance_coverage_end` DATE
  - `insurance_type` VARCHAR(64) – `'vehicle'`, `'property'`, `'crop'`, `'liability'`
  - `insurance_asset_description` TEXT

- **AFFITTI** (`document_type = 'rent'`):
  - `rent_contract_id` INT (FK → rent_contracts, OBBLIGATORIO)
  - `rent_period_month` INT (1-12)
  - `rent_period_year` INT
  - `rent_property_description` VARCHAR(255)

- **MAV/CBILL** (`document_type = 'mav'` | `'cbill'`):
  - `payment_code` VARCHAR(64) – codice avviso
  - `creditor_entity` VARCHAR(255) – ente creditore

- **SCONTRINI** (`document_type = 'receipt'`):
  - `receipt_merchant` VARCHAR(255)
  - `receipt_category` VARCHAR(64)

- **TRIBUTI/TASSE** (`document_type = 'tax'`):
  - `tax_type` VARCHAR(64) – `'imu'`, `'tari'`, `'tasi'`, `'canone'`
  - `tax_period_year` INT
  - `tax_period_description` VARCHAR(128)

##### Relazioni

- 1:N con `invoice_lines` (solo per document_type='invoice')
- 1:N con `vat_summaries` (solo per document_type='invoice')
- 1:N con `payments` (scadenze, per TUTTI i tipi)
- 1:N con `delivery_notes` (DDT, solo per fatture differite)
- 1:N con `notes` (note, per TUTTI i tipi)
- 1:N con `import_logs` (log, per TUTTI i tipi)
- N:1 con `rent_contracts` (solo per document_type='rent')

---

### 3.3. Dettagli Documenti (Tabelle Specializzate)

#### `invoice_lines`

Righe di dettaglio delle **fatture**.

```sql
CREATE TABLE invoice_lines (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT NOT NULL COMMENT 'FK a documents (document_type=invoice)',
  category_id INT COMMENT 'FK a categories',
  line_number INT NOT NULL,
  description TEXT,
  quantity DECIMAL(15,4),
  unit_of_measure VARCHAR(16),
  unit_price DECIMAL(15,4),
  discount_percentage DECIMAL(5,2),
  discount_amount DECIMAL(15,2),
  taxable_amount DECIMAL(15,2),
  vat_rate DECIMAL(5,2),
  vat_amount DECIMAL(15,2),
  total_line_amount DECIMAL(15,2),
  sku_code VARCHAR(64),
  internal_code VARCHAR(64),
  notes TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (category_id) REFERENCES categories(id)
);
```

**Indici:**
- `ix_invoice_lines_document_id` (document_id)
- `ix_invoice_lines_category_id` (category_id)
- `ix_invoice_lines_created_at` (created_at)

#### `vat_summaries`

Riepiloghi IVA per **fatture**.

```sql
CREATE TABLE vat_summaries (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT NOT NULL COMMENT 'FK a documents (document_type=invoice)',
  vat_rate DECIMAL(5,2),
  taxable_amount DECIMAL(15,2),
  vat_amount DECIMAL(15,2),
  vat_nature VARCHAR(8) COMMENT 'N1, N2, N3, N4, N5, N6, N7',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);
```

**Indici:**
- `ix_vat_summaries_document_id` (document_id)
- `ix_vat_summaries_created_at` (created_at)

#### `rent_contracts`

Contratti di **affitto** (generano documenti mensili in `documents` con document_type='rent').

```sql
CREATE TABLE rent_contracts (
  id INT PRIMARY KEY AUTO_INCREMENT,
  contract_number VARCHAR(64) NOT NULL UNIQUE,
  supplier_id INT NOT NULL COMMENT 'Proprietario',
  legal_entity_id INT NOT NULL COMMENT 'Conduttore',
  property_description TEXT,
  property_address VARCHAR(255),
  monthly_amount DECIMAL(15,2) NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE,
  payment_day INT DEFAULT 1 COMMENT 'Giorno del mese (1-31) per pagamento rata',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  notes TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
  FOREIGN KEY (legal_entity_id) REFERENCES legal_entities(id)
);
```

**Indici:**
- `idx_rent_contracts_number` (UNIQUE su contract_number)
- `idx_rent_contracts_supplier` (supplier_id)
- `idx_rent_contracts_legal_entity` (legal_entity_id)
- `idx_rent_contracts_active` (is_active, start_date)

---

### 3.4. Scadenze e Pagamenti

Questo è il "cuore" del sistema di gestione finanziaria.

#### `payments`

Tabella delle **scadenze** e dello **stato di pagamento** per **TUTTI i documenti**.

```sql
CREATE TABLE payments (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT NOT NULL COMMENT 'FK a documents (qualsiasi tipo)',
  payment_document_id INT COMMENT 'FK a payment_documents (se riconciliato)',
  due_date DATE,
  expected_amount DECIMAL(15,2),
  payment_terms VARCHAR(128) COMMENT 'Condizioni pagamento (es. 30gg DFFM)',
  payment_method VARCHAR(64) COMMENT 'Metodo previsto',
  paid_date DATE,
  paid_amount DECIMAL(15,2),
  status VARCHAR(32) NOT NULL DEFAULT 'unpaid',
  notes TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (payment_document_id) REFERENCES payment_documents(id),
  
  CONSTRAINT chk_payments_status 
    CHECK (status IN ('unpaid', 'planned', 'pending', 'partial', 
                      'paid', 'cancelled', 'overdue'))
);
```

**Indici:**
- `ix_payments_document_id` (document_id)
- `ix_payments_due_status` (status, due_date)
- `ix_payments_due_date` (due_date)
- `ix_payments_paid_date` (paid_date)
- `ix_payments_created_at` (created_at)
- `fk_payments_payment_document` (payment_document_id)

**Semantica:**

- **Fonte unica delle scadenze**: tutto lo scadenziario legge solo da questa tabella
- `documents.due_date` è solo metadata di riferimento
- `status` VALUES:
  - `'unpaid'` – scadenza non pagata
  - `'planned'` – pagamento pianificato
  - `'pending'` – pagamento in corso
  - `'partial'` – pagamento parziale (paid_amount < expected_amount)
  - `'paid'` – completamente pagato
  - `'cancelled'` – annullato
  - `'overdue'` – scaduto

#### `payment_documents`

PDF di **movimenti bancari/pagamenti reali** (estratti conto, ricevute).

```sql
CREATE TABLE payment_documents (
  id INT PRIMARY KEY AUTO_INCREMENT,
  supplier_id INT NOT NULL COMMENT 'Fornitore relativo al pagamento',
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(500) NOT NULL,
  payment_type VARCHAR(32) NOT NULL DEFAULT 'sconosciuto',
  status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
  uploaded_at DATETIME NOT NULL,
  parsed_amount DECIMAL(12,2),
  parsed_payment_date DATE,
  parsed_document_number VARCHAR(100) COMMENT 'Numero documento pagato (da OCR)',
  parse_error_message TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
  
  CONSTRAINT chk_payment_documents_payment_type 
    CHECK (payment_type IN ('sconosciuto', 'bonifico', 'rid', 'mav', 
                            'cbill', 'assegno', 'contanti', 'carta', 'f24')),
  
  CONSTRAINT chk_payment_documents_status 
    CHECK (status IN ('pending_review', 'imported', 'reconciled', 
                      'partial', 'ignored'))
);
```

**Indici:**
- `idx_payment_documents_supplier` (supplier_id)
- `idx_payment_documents_supplier_date` (supplier_id, parsed_payment_date DESC)
- `idx_payment_documents_status` (status)
- `idx_payment_documents_date` (parsed_payment_date)

**Semantica:**

- `payment_type` indica il metodo di pagamento rilevato dal PDF
- `status` indica lo stato di riconciliazione con le scadenze:
  - `'pending_review'` – caricato, da verificare
  - `'imported'` – importato, pronto per riconciliazione
  - `'reconciled'` – completamente riconciliato
  - `'partial'` – parzialmente riconciliato
  - `'ignored'` – ignorato (non da riconciliare)

#### `payment_document_links`

Mapping **M:N** tra movimenti bancari e scadenze (quando un singolo bonifico copre più scadenze).

```sql
CREATE TABLE payment_document_links (
  id INT PRIMARY KEY AUTO_INCREMENT,
  payment_id INT NOT NULL COMMENT 'FK a payments',
  payment_document_id INT NOT NULL COMMENT 'FK a payment_documents',
  linked_amount DECIMAL(15,2) NOT NULL COMMENT 'Importo di questa scadenza coperto da questo movimento',
  linked_at DATETIME NOT NULL,
  notes TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE,
  FOREIGN KEY (payment_document_id) REFERENCES payment_documents(id) ON DELETE CASCADE,
  
  UNIQUE KEY idx_unique_payment_link (payment_id, payment_document_id)
);
```

**Indici:**
- `idx_unique_payment_link` (UNIQUE su payment_id, payment_document_id)
- `idx_payment_document_links_payment` (payment_id)
- `idx_payment_document_links_document` (payment_document_id)
- `idx_payment_document_links_linked_at` (linked_at)

---

### 3.5. DDT e Bolle

#### `delivery_notes`

Tabella per gestire i **DDT** (Documenti di Trasporto) e bolle di consegna.

```sql
CREATE TABLE delivery_notes (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT COMMENT 'FK a documents se è una fattura differita',
  supplier_id INT NOT NULL,
  legal_entity_id INT NOT NULL,
  ddt_number VARCHAR(64) NOT NULL,
  ddt_date DATE NOT NULL,
  goods_description TEXT,
  status VARCHAR(32) NOT NULL DEFAULT 'unmatched',
  source VARCHAR(32) NOT NULL DEFAULT 'manual',
  file_name VARCHAR(255),
  file_path VARCHAR(500),
  notes TEXT,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  FOREIGN KEY (document_id) REFERENCES documents(id),
  FOREIGN KEY (supplier_id) REFERENCES suppliers(id),
  FOREIGN KEY (legal_entity_id) REFERENCES legal_entities(id),
  
  CONSTRAINT chk_delivery_notes_status 
    CHECK (status IN ('unmatched', 'matched', 'missing', 'ignored')),
  
  CONSTRAINT chk_delivery_notes_source 
    CHECK (source IN ('xml_expected', 'pdf_import', 'manual'))
);
```

**Indici:**
- `idx_delivery_notes_document` (document_id)
- `idx_delivery_notes_supplier` (supplier_id)
- `idx_delivery_notes_legal_entity` (legal_entity_id)
- `idx_delivery_notes_status` (status)
- `idx_delivery_notes_ddt_number` (ddt_number, ddt_date)

**Semantica:**

- `source` indica l'origine del DDT:
  - `'xml_expected'` – citato nel XML di fattura differita (atteso)
  - `'pdf_import'` – importato da PDF scansionato (reale)
  - `'manual'` – inserito manualmente
  
- `status` indica lo stato di matching:
  - `'unmatched'` – non ancora abbinato
  - `'matched'` – abbinato con documento
  - `'missing'` – atteso ma non trovato
  - `'ignored'` – ignorato

**Workflow:**

1. All'import della fattura differita: per ogni DDT citato nel XML → si crea riga con `source='xml_expected'`, `status='unmatched'`
2. All'import PDF delle bolle: si crea riga con `source='pdf_import'`, `status='unmatched'`
3. Matching automatico/manuale: se atteso trova reale → `status='matched'`, `document_id` impostato

---

### 3.6. Classificazione

#### `categories`

Categorie di spesa per classificare le righe fattura.

```sql
CREATE TABLE categories (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(128) NOT NULL UNIQUE,
  description TEXT,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

**Indici:**
- `idx_categories_name` (UNIQUE su name)
- `idx_categories_active` (is_active)

**Relazione:**
- 1:N con `invoice_lines.category_id`

#### `notes`

Note operative e commenti sui **documenti** (qualsiasi tipo).

```sql
CREATE TABLE notes (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT NOT NULL COMMENT 'FK a documents (qualsiasi tipo)',
  user_id INT COMMENT 'FK a users',
  content TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Indici:**
- `idx_notes_document` (document_id)
- `idx_notes_user` (user_id)
- `idx_notes_created_at` (created_at)

---

### 3.7. Logging e Impostazioni Applicative

#### `import_logs`

Log dei file XML/PDF importati.

```sql
CREATE TABLE import_logs (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT COMMENT 'FK a documents (se import ha generato un documento)',
  file_name VARCHAR(255) NOT NULL,
  file_hash VARCHAR(64),
  import_source VARCHAR(128),
  status VARCHAR(32) NOT NULL,
  message TEXT,
  created_at DATETIME NOT NULL,
  
  FOREIGN KEY (document_id) REFERENCES documents(id),
  
  CONSTRAINT chk_import_logs_status 
    CHECK (status IN ('success', 'error', 'warning', 'duplicate'))
);
```

**Indici:**
- `idx_import_logs_document` (document_id)
- `idx_import_logs_file_hash` (file_hash)
- `idx_import_logs_status` (status)
- `idx_import_logs_created_at` (created_at)

**Uso:**
- Audit trail degli import
- Diagnostica errori di parsing o duplicati
- Prevenzione re-import dello stesso file (via file_hash)

#### `app_settings`

Configurazioni globali modificabili a runtime.

```sql
CREATE TABLE app_settings (
  id INT PRIMARY KEY AUTO_INCREMENT,
  setting_key VARCHAR(191) NOT NULL UNIQUE,
  value TEXT,
  description VARCHAR(255),
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

**Indici:**
- `idx_app_settings_key` (UNIQUE su setting_key)

#### `users`

Utenti dell'applicazione.

```sql
CREATE TABLE users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL UNIQUE,
  full_name VARCHAR(128),
  email VARCHAR(255) UNIQUE,
  role VARCHAR(32) NOT NULL DEFAULT 'user',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  
  CONSTRAINT chk_users_role 
    CHECK (role IN ('admin', 'user', 'readonly'))
);
```

**Indici:**
- `ix_users_username` (UNIQUE su username)
- `email` (UNIQUE su email)
- `ix_users_created_at` (created_at)

**Relazioni:**
- 1:N con `notes` (autore delle note)

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
- `documents.physical_copy_status`
- `documents.invoice_type` (con vincolo condizionale)
- `documents.insurance_type` (con vincolo condizionale)
- `documents.rent_contract_id` (con vincolo condizionale)
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
- `payment_document_links.(payment_id, payment_document_id)` → UNIQUE

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

### 4.5. Indici Strategici

Il database implementa una strategia di indicizzazione multi-livello:

**Indici Singoli:**
- Su tutte le foreign keys per JOIN veloci
- Su campi usati frequentemente in WHERE (status, date)
- Su campi UNIQUE per integrità

**Indici Compound:**
- `(entity_id, date DESC)` per listing cronologici paginati
- `(status, date)` per dashboard filtrate per stato
- `(type, date)` per report per tipo documento

**Indici Specializzati:**
- `file_hash` in import_logs per prevenzione duplicati
- `(ddt_number, ddt_date)` per ricerca DDT veloce

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
  technician_name VARCHAR(128),
  next_service_date DATE,
  ...
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
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

### Fatture con DDT Mancanti
```sql
SELECT 
  d.id,
  d.document_number,
  d.document_date,
  dn.ddt_number,
  dn.ddt_date
FROM documents d
JOIN delivery_notes dn ON dn.document_id = d.id
WHERE d.document_type = 'invoice'
  AND d.invoice_type = 'deferred'
  AND dn.source = 'xml_expected'
  AND dn.status = 'missing';
```

### Pagamenti da Riconciliare
```sql
SELECT 
  pd.id,
  pd.file_name,
  pd.parsed_amount,
  pd.parsed_payment_date,
  s.name AS supplier_name
FROM payment_documents pd
JOIN suppliers s ON s.id = pd.supplier_id
WHERE pd.status IN ('pending_review', 'imported')
ORDER BY pd.parsed_payment_date DESC;
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

rent_contracts (1) ──< (N) documents (solo rent)
```

---

## 8. Statistiche Database (dal dump SQL)

**Engine:** InnoDB (tutte le tabelle)  
**Charset:** utf8mb4  
**Collation:** utf8mb4_unicode_ci  

**Tabelle Principali (con AUTO_INCREMENT):**
- `documents`: AUTO_INCREMENT=30
- `invoice_lines`: AUTO_INCREMENT=55
- `vat_summaries`: AUTO_INCREMENT=23
- `payments`: AUTO_INCREMENT=23
- `payment_documents`: AUTO_INCREMENT=2
- `suppliers`: AUTO_INCREMENT=20
- `categories`: AUTO_INCREMENT non definito
- `legal_entities`: AUTO_INCREMENT=4

**Caratteristiche Tecniche:**
- Foreign Keys con ON DELETE CASCADE dove appropriato (dettagli dipendenti)
- Foreign Keys senza cascade per anagrafiche (preservazione dati)
- CHECK constraints estensivi per garantire integrità dei dati
- Indici compound ottimizzati per query più frequenti

---

## 9. Note Finali

- Questo schema è **production-ready** per gestire fatture, F24, assicurazioni, MAV, CBILL, scontrini, affitti, tributi.
- L'estensione a nuovi tipi è **immediata** (aggiungi `document_type` + colonne nullable).
- La consistenza dei dati è garantita da **CHECK constraints** e **FK**.
- Le performance sono ottimizzate con **indici compound** sui path di query più frequenti.
- Il modello è **futureproof**: può evolvere senza refactor massivi.
- **Separazione netta** tra documenti economici (`documents`) e movimenti bancari (`payment_documents`).
- **Riconciliazione flessibile** via `payment_document_links` per gestire casistiche complesse.
- **Tracciabilità completa** via `import_logs` e `notes`.

---

## 10. Riferimenti Implementativi

**File SQL di riferimento:** `databaseAcquistiv3.sql`  
**Data dump:** 11 Dicembre 2025, ore 15:41  
**Versione MySQL:** 8.0.44

**Note sulla migrazione:**
- Il dump include anche database `world` e `sys` (demo/system), non pertinenti al gestionale
- Il database applicativo effettivo è `databaseacquisti`
- Tutti gli AUTO_INCREMENT values riflettono lo stato di sviluppo/test attuale