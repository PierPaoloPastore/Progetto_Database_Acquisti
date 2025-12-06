---

# Progetto: Gestionale Acquisti - Migrazione a Supertipo Documents

## Contesto
Stiamo migrando da un'architettura con `invoices` come tabella principale a un'architettura con `documents` come supertipo per tutti i documenti economici (fatture, F24, assicurazioni, MAV, CBILL, scontrini, affitti, tributi).

## Database Schema (ATTUALE)
Il database usa **Single Table Inheritance** con la tabella `documents` come supertipo:

### Tabella `documents` (45+ colonne)
- **Discriminatore**: `document_type` VARCHAR(32) - valori: 'invoice', 'f24', 'insurance', 'mav', 'cbill', 'receipt', 'rent', 'tax', 'other'
- **Colonne comuni**: supplier_id, legal_entity_id, document_number, document_date, due_date, registration_date, total_taxable_amount, total_vat_amount, total_gross_amount, doc_status, import_source, file_name, file_path, imported_at, physical_copy_status, physical_copy_requested_at, physical_copy_received_at, created_at, updated_at
- **Colonne specifiche INVOICE**: invoice_type
- **Colonne specifiche F24**: f24_period_from, f24_period_to, f24_tax_type, f24_payment_code
- **Colonne specifiche INSURANCE**: insurance_policy_number, insurance_coverage_start, insurance_coverage_end, insurance_type, insurance_asset_description
- **Colonne specifiche RENT**: rent_contract_id, rent_period_month, rent_period_year, rent_property_description
- **Colonne specifiche MAV/CBILL**: payment_code, creditor_entity
- **Colonne specifiche RECEIPT**: receipt_merchant, receipt_category
- **Colonne specifiche TAX**: tax_type, tax_period_year, tax_period_description

### Tabelle Dipendenti
- `invoice_lines` → FK `document_id` (non più `invoice_id`)
- `vat_summaries` → FK `document_id`
- `payments` → FK `document_id`
- `delivery_notes` → FK `document_id`
- `notes` → FK `document_id`
- `import_logs` → FK `document_id`
- `rent_contracts` → nuova tabella per contratti affitto

### Modifiche Anagrafiche
- `suppliers.tax_code` → rinominato a `fiscal_code`
- `legal_entities.tax_code` → rimosso (era sempre NULL)
- `payment_documents.supplier_id` → aggiunto

## File di Riferimento
- `docs/DB_ARCHITECTURE.md`: Documentazione completa architettura database
- `docs/ARCHITECTURE.md`: Documentazione architettura applicazione
- `schema_final_documents.sql`: Schema SQL eseguito sul database

## Regole Implementazione
- Import `db` da `app.extensions`
- Usare `datetime.utcnow` per timestamp defaults
- Type hints dove appropriato
- Docstring sulle classi principali
- Relationships con backref chiari
- Cascade 'all, delete-orphan' per ownership

---
