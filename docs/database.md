Last updated: 2026-04-14

# Architettura Database

Schema reale corrente del database del Gestionale Acquisti, allineato al DDL MySQL fornito dal repository operativo.

Versione logica: `documents` come supertipo unico, con tabelle di dettaglio per righe, IVA, pagamenti, DDT, note e audit.

---

## 1. Obiettivi del modello

Il database copre l'intero ciclo passivo:

1. import documenti di acquisto;
2. revisione e conferma dei documenti;
3. classificazione per categorie;
4. gestione copie fisiche e allegati;
5. pianificazione e registrazione pagamenti;
6. gestione DDT e matching;
7. logging applicativo e audit.

Principi strutturali:

- `documents` è il supertipo centrale;
- le anagrafiche (`suppliers`, `legal_entities`, `bank_accounts`) sono separate;
- i pagamenti usano `payments` per scadenze/stati e `payment_documents` per i PDF bancari;
- le FK sono esplicite e i `CHECK` proteggono i campi enumerativi.

---

## 2. Panoramica delle tabelle

### Anagrafiche

- `suppliers`
- `legal_entities`
- `bank_accounts`
- `users`

### Documenti e dettagli

- `documents`
- `invoice_lines`
- `vat_summaries`
- `rent_contracts`

### Pagamenti

- `payments`
- `payment_documents`
- `payment_document_links`

### Logistica e supporto

- `delivery_notes`
- `delivery_note_lines`
- `notes`
- `categories`

### Logging e configurazione

- `import_logs`
- `document_audit_logs`
- `app_settings`

---

## 3. Anagrafiche

### `suppliers`

Anagrafica fornitori.

Campi rilevanti:

- `id` PK auto increment
- `name` obbligatorio
- `vat_number`, `fiscal_code`
- `sdi_code`, `pec_email`, `iban`, contatti e indirizzi
- `typical_due_rule`, `typical_due_days`
- `is_active`

Vincoli e indici:

- `PRIMARY KEY (id)`
- `UNIQUE uq_suppliers_vat_cf (vat_number, fiscal_code)`
- `idx_suppliers_name`
- `idx_suppliers_created_at`

Nota:
- la coppia `(vat_number, fiscal_code)` identifica il fornitore nel DB reale; la sola P.IVA non è unica.

### `legal_entities`

Intestazioni aziendali interne.

Campi rilevanti:

- `id` PK auto increment
- `name` obbligatorio
- `vat_number` unico
- `fiscal_code`
- `address`, `city`, `country`
- `is_active`

Vincoli e indici:

- `PRIMARY KEY (id)`
- `UNIQUE idx_legal_entities_vat_unique (vat_number)`
- `idx_legal_entities_name`
- `idx_legal_entities_created_at`

### `bank_accounts`

Conti bancari associati alle intestazioni.

Campi rilevanti:

- `iban` PK
- `legal_entity_id` FK obbligatoria
- `name`
- `notes`

Vincoli e indici:

- `PRIMARY KEY (iban)`
- `UNIQUE uq_bank_accounts_iban (iban)`
- `idx_bank_accounts_legal_entity_id`
- FK `legal_entity_id -> legal_entities.id ON DELETE CASCADE`

---

## 4. Supertipo documenti: `documents`

Tabella centrale del dominio.

### Campi comuni principali

- `id`
- `document_type`
- `supplier_id`
- `legal_entity_id`
- `document_number`
- `document_date`
- `due_date`
- `registration_date`
- `total_taxable_amount`
- `total_vat_amount`
- `total_gross_amount`
- `doc_status`
- `print_status`
- `import_source`
- `file_name`, `file_path`
- `imported_at`
- `physical_copy_status`
- `physical_copy_file_path`
- `physical_copy_requested_at`, `physical_copy_received_at`
- `note`
- `is_paid`
- `created_at`, `updated_at`

### Colonne specifiche per tipo

- fatture / note di credito: `invoice_type`
- F24: `f24_period_from`, `f24_period_to`, `f24_tax_type`, `f24_payment_code`
- assicurazioni: `insurance_policy_number`, `insurance_coverage_*`, `insurance_type`, `insurance_asset_description`
- affitti: `rent_contract_id`, `rent_period_month`, `rent_period_year`, `rent_property_description`
- MAV / CBILL: `payment_code`, `creditor_entity`
- scontrini: `receipt_merchant`, `receipt_category`
- tributi: `tax_type`, `tax_period_year`, `tax_period_description`

### Vincoli

- FK verso `suppliers`, `legal_entities`, `rent_contracts`
- `chk_documents_type`
- `chk_documents_status`
- `chk_documents_physical_copy_status`
- `chk_documents_invoice_type`
- `chk_documents_f24_code`
- `chk_documents_insurance_policy`

### Valori applicativi importanti

`document_type`:

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

`doc_status`:

- `pending_physical_copy`
- `verified`
- `archived`

`physical_copy_status`:

- `missing`
- `requested`
- `received`
- `uploaded`
- `not_required`

### Indici reali presenti

- `idx_documents_type (document_type)`
- `idx_documents_supplier_date (supplier_id, document_date DESC)`
- `idx_documents_legal_entity_date (legal_entity_id, document_date DESC)`
- `idx_documents_status_created (doc_status, created_at DESC)`
- `idx_documents_document_date (document_date)`
- `idx_documents_supplier_type (supplier_id, document_type)`
- `idx_documents_print_status (print_status)`

Nota operativa:
- nel DB reale `supplier_id` e `legal_entity_id` sono `NOT NULL`.

---

## 5. Tabelle di dettaglio documento

### `invoice_lines`

Righe di fattura / documento con dettaglio articoli.

Campi rilevanti:

- `document_id` FK obbligatoria
- `category_id` FK opzionale
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

Indici:

- `ix_invoice_lines_document_id`
- `ix_invoice_lines_category_id`
- `ix_invoice_lines_created_at`

### `vat_summaries`

Riepiloghi IVA per documento.

Campi rilevanti:

- `document_id`
- `vat_rate`
- `taxable_amount`
- `vat_amount`
- `vat_nature`

Indici:

- `ix_vat_summaries_document_id`
- `ix_vat_summaries_created_at`

### `rent_contracts`

Contratti affitto che possono generare documenti `rent`.

Campi rilevanti:

- `contract_number` unico
- `supplier_id`
- `legal_entity_id`
- `monthly_amount`
- `start_date`, `end_date`
- `payment_day`
- `is_active`

Indici:

- `idx_rent_contracts_number`
- `idx_rent_contracts_supplier`
- `idx_rent_contracts_legal_entity`
- `idx_rent_contracts_active (is_active, start_date)`

---

## 6. Pagamenti

### `payments`

Fonte dati delle scadenze e dello stato di pagamento.

Campi rilevanti:

- `document_id` FK obbligatoria
- `payment_document_id` FK opzionale
- `due_date`
- `expected_amount`
- `payment_terms`
- `payment_method`
- `paid_date`
- `paid_amount`
- `status`
- `notes`
- `created_at`, `updated_at`

Vincoli:

- FK `document_id -> documents.id ON DELETE CASCADE`
- FK `payment_document_id -> payment_documents.id`
- `chk_payments_status`

Valori ammessi in `status`:

- `unpaid`
- `planned`
- `pending`
- `partial`
- `paid`
- `cancelled`
- `overdue`

Indici reali:

- `ix_payments_document_id`
- `ix_payments_due_status (status, due_date)`
- `ix_payments_due_date`
- `ix_payments_paid_date`
- `ix_payments_created_at`
- `fk_payments_payment_document` su `payment_document_id`

Nota:
- `payment_method` è una `VARCHAR(64)` non indicizzata nel DB attuale.
- applicativamente vengono usati i codici FatturaPA `MP01`-`MP22`.

### `payment_documents`

PDF e metadati del movimento bancario reale.

Campi rilevanti:

- `supplier_id`
- `file_name`
- `file_path`
- `payment_type`
- `status`
- `uploaded_at`
- `parsed_amount`
- `parsed_payment_date`
- `parsed_document_number`
- `parse_error_message`
- `bank_account_iban`

Vincoli:

- FK verso `suppliers`
- FK `bank_account_iban -> bank_accounts.iban ON DELETE SET NULL`
- `chk_payment_documents_payment_type`
- `chk_payment_documents_status`

Valori ammessi in `payment_type`:

- `sconosciuto`
- `bonifico`
- `rid`
- `mav`
- `cbill`
- `assegno`
- `contanti`
- `carta`
- `f24`

Valori ammessi in `status`:

- `pending_review`
- `imported`
- `reconciled`
- `partial`
- `ignored`

Indici reali:

- `idx_payment_documents_supplier`
- `idx_payment_documents_supplier_date (supplier_id, parsed_payment_date DESC)`
- `idx_payment_documents_status`
- `idx_payment_documents_date`
- indice FK su `bank_account_iban`

### `payment_document_links`

Tabella ponte M:N tra `payment_documents` e `payments`.

Campi reali:

- `id`
- `payment_document_id`
- `payment_id`
- `allocated_amount`
- `created_at`

Indici reali:

- `ix_payment_document_links_payment_document`
- `ix_payment_document_links_payment`

Nota importante:
- la tabella esiste nello schema reale;
- l'applicazione corrente usa soprattutto `payments.payment_document_id` e il documento condiviso di batch;
- `payment_document_links` va quindi considerata parte dello schema supportato, ma non il percorso principale oggi usato dalle route web correnti.

---

## 7. DDT e logistica

### `delivery_notes`

DDT attesi da XML o importati da PDF/manualmente.

Campi rilevanti:

- `document_id`
- `supplier_id`
- `legal_entity_id`
- `ddt_number`
- `ddt_date`
- `total_amount`
- `file_path`, `file_name`
- `source`
- `import_source`
- `imported_at`
- `status`

Vincoli:

- FK verso `documents`, `suppliers`, `legal_entities`
- `chk_delivery_notes_source`
- `chk_delivery_notes_status`

Valori `source`:

- `xml_expected`
- `pdf_import`
- `manual`

Valori `status`:

- `unmatched`
- `matched`
- `missing`
- `linked`
- `ignored`

Indici reali:

- `ix_delivery_notes_supplier`
- `ix_delivery_notes_supplier_date_number (supplier_id, ddt_date, ddt_number)`
- `ix_delivery_notes_document`
- `ix_delivery_notes_status`
- indice FK su `legal_entity_id`

### `delivery_note_lines`

Dettaglio righe DDT.

Campi rilevanti:

- `delivery_note_id`
- `line_number`
- `description`
- `item_code`
- `quantity`
- `uom`
- `amount`
- `notes`

Vincoli e indici:

- FK `delivery_note_id -> delivery_notes.id ON DELETE CASCADE`
- `UNIQUE uq_dnl_note_line (delivery_note_id, line_number)`
- `idx_dnl_delivery_note`
- `idx_dnl_item_code`

---

## 8. Classificazione, note e audit

### `categories`

Categorie di spesa.

Campi rilevanti:

- `name` unico
- `description`
- `vat_rate`
- `is_active`

Indici:

- `ix_categories_name`
- `ix_categories_created_at`

### `notes`

Note operative sui documenti.

Campi rilevanti:

- `document_id`
- `user_id`
- `content`
- `created_at`

Indici:

- `ix_notes_document_id`
- `ix_notes_user_id`
- `ix_notes_created_at`

### `document_audit_logs`

Storico modifiche documento.

Campi rilevanti:

- `document_id`
- `action`
- `payload`
- `created_at`

Indici:

- `idx_document_audit_document_id`
- `idx_document_audit_created_at`
- `idx_document_audit_action`

---

## 9. Logging e configurazione

### `import_logs`

Log import documenti.

Campi rilevanti:

- `document_id`
- `file_name`
- `file_hash`
- `import_source`
- `status`
- `message`
- `created_at`

Valori `status`:

- `success`
- `error`
- `warning`
- `duplicate`

Indici:

- `ix_import_logs_document_id`
- `ix_import_logs_file_hash`
- `ix_import_logs_status`
- `ix_import_logs_file_name`
- `ix_import_logs_created_at`

### `app_settings`

Configurazioni runtime applicative.

Campi rilevanti:

- `setting_key` unico
- `value`
- `description`
- `created_at`, `updated_at`

### `users`

Utenti applicativi.

Campi rilevanti:

- `username` unico
- `email` unica
- `role`
- `is_active`

Valori `role`:

- `admin`
- `user`
- `readonly`

---

## 10. Relazioni principali

Schema logico sintetico:

```text
suppliers (1) -> (N) documents
legal_entities (1) -> (N) documents
legal_entities (1) -> (N) bank_accounts

documents (1) -> (N) invoice_lines
documents (1) -> (N) vat_summaries
documents (1) -> (N) payments
documents (1) -> (N) delivery_notes
documents (1) -> (N) notes
documents (1) -> (N) import_logs
documents (1) -> (N) document_audit_logs

payments (N) -> (1) payment_documents   [opzionale]
payment_documents (1) -> (N) payment_document_links
payments (1) -> (N) payment_document_links

delivery_notes (1) -> (N) delivery_note_lines
categories (1) -> (N) invoice_lines
users (1) -> (N) notes
rent_contracts (1) -> (N) documents
```

---

## 11. Note operative sullo schema reale

### Stato documentazione vs runtime

- il DB contiene `payment_document_links`, ma il flusso web corrente non lo usa come percorso principale;
- `documents.is_paid` esiste nello schema reale ed è usato come flag rapido applicativo;
- `documents.print_status` è parte dello schema reale e supporta la gestione documenti programmati/stampati;
- `physical_copy_status` nel DB include anche `uploaded`, oltre ai valori storici più vecchi.

### Indici già presenti

Per il volume dati attuale, il DB è già discretamente indicizzato su:

- foreign key principali;
- date operative;
- alcuni filtri di stato;
- combinazioni fornitore/data o intestazione/data.

Eventuali futuri indici aggiuntivi vanno valutati separatamente e non fanno parte dello stato documentale corrente.

---

## 12. Fonte di verità di questo documento

Questa pagina descrive lo schema effettivamente risultante dal DDL MySQL corrente fornito per:

- `app_settings`
- `bank_accounts`
- `categories`
- `delivery_notes`
- `delivery_note_lines`
- `document_audit_logs`
- `documents`
- `import_logs`
- `invoice_lines`
- `legal_entities`
- `notes`
- `payment_documents`
- `payment_document_links`
- `payments`
- `rent_contracts`
- `suppliers`
- `users`
- `vat_summaries`

Quando cambia lo schema reale, questa è la documentazione da aggiornare per prima.
