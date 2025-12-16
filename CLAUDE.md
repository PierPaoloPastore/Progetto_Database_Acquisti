# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Monolithic Flask app (Python 3.12 + MySQL) managing the full lifecycle of purchase documents (Italian "ciclo passivo"). The system centers on a **unified `documents` supertype** using Single Table Inheritance to support invoices (FatturaPA), F24 tax forms, insurance, rent, receipts, MAV/CBILL, and other economic documents.

Key capabilities:
- FatturaPA XML/P7M import with parsing, supplier/legal entity registry, and delivery note tracking
- Document review workflow with states: `imported`, `verified`, `rejected`, `cancelled`, `archived`
- Physical copy management (scan tracking)
- Payment scheduling via `payments` table with reconciliation to bank PDF documents
- Categories, notes, export/reporting (CSV, IVA summaries, supplier statements)

## Essential Commands

### Development
```bash
# Install dependencies (use virtualenv)
pip install -r requirements.txt

# Create database tables
python manage.py create-db

# Run development server (Flask)
python manage.py runserver
# Defaults to http://0.0.0.0:5000
# Customize with FLASK_RUN_HOST and FLASK_RUN_PORT env vars
```

### Database Configuration
Edit `config.py` → `DevConfig` class to set MySQL credentials:
```python
SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:password@localhost:3306/gestionale_acquisti"
```

Environment variables supported:
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`
- `DATABASE_URL` (overrides all)

## Architecture Overview

### Layer Structure
```
config.py / manage.py          # Config & app factory
app/__init__.py                # create_app(), blueprint registration
app/extensions.py              # SQLAlchemy (db), JSON logging
app/middleware/auth_stub.py    # Stub auth (g.current_user)

app/models/*                   # SQLAlchemy ORM (domain model)
app/repositories/*             # Data access (query encapsulation)
app/services/*                 # Business logic
app/parsers/*                  # FatturaPA XML parsing (lxml-based DTOs)

app/web/*                      # Flask blueprints (HTML routes)
app/api/*                      # JSON API endpoints
app/templates/*                # Jinja2 templates
app/static/*                   # CSS/JS
```

### Critical Patterns

**Repository + Unit of Work (MANDATORY for data access)**
- All database queries MUST go through repositories in `app/repositories/`
- Transactional coordination via `UnitOfWork` in `app/services/unit_of_work.py`
- Pattern: `with UnitOfWork() as uow: ... uow.commit()`
- Repositories expose query methods; services orchestrate business logic
- Never bypass this pattern with raw `db.session` calls

**Single Table Inheritance for Documents**
- `documents` table = supertype for ALL economic documents
- `document_type` column discriminates: `'invoice'`, `'f24'`, `'insurance'`, `'mav'`, `'cbill'`, `'receipt'`, `'rent'`, `'tax'`, `'other'`
- Common columns: `supplier_id`, `legal_entity_id`, `document_number`, `document_date`, `doc_status`, amounts
- Type-specific columns: nullable (e.g., `invoice_type`, `f24_payment_code`, `insurance_policy_number`)
- Specialized detail tables: `invoice_lines`, `vat_summaries`, `rent_contracts`
- All documents share: `payments`, `notes`, `import_logs`, `delivery_notes` (where applicable)

**Source of Truth Rules**
- Payment deadlines: ONLY `payments` table (not `documents.due_date`, which is metadata)
- Bank/payment PDFs: `payment_documents` table
- Reconciliation: M:N via `payment_document_links` (one bank transfer can cover multiple deadlines)

### Key Models (`app/models/`)

- `Document` (supertype, `documents` table)
  - Relationships: `supplier`, `legal_entity`, `invoice_lines`, `vat_summaries`, `payments`, `delivery_notes`, `notes`, `import_logs`, `rent_contract`
  - Helper properties: `is_invoice`, `is_f24`, `is_insurance`, etc.

- `Payment` (deadlines/installments for ANY document type)
  - Fields: `due_date`, `expected_amount`, `paid_date`, `paid_amount`, `status`, `payment_method`, `payment_terms`, `notes`
  - Status enum: `'unpaid'`, `'planned'`, `'pending'`, `'partial'`, `'paid'`, `'cancelled'`, `'overdue'`
  - FK: `document_id` → `documents.id`, `payment_document_id` → `payment_documents.id` (nullable)

- `PaymentDocument` (bank PDFs)
  - Fields: `supplier_id`, `file_name`, `file_path`, `payment_type`, `status`, `parsed_amount`, `parsed_payment_date`
  - Status enum: `'pending_review'`, `'imported'`, `'reconciled'`, `'partial'`, `'ignored'`

- `DeliveryNote` (DDT tracking)
  - Sources: `'xml_expected'` (from deferred invoice XML), `'pdf_import'` (scanned PDF), `'manual'`
  - Status: `'unmatched'`, `'matched'`, `'missing'`, `'ignored'`

### Services (`app/services/`)

- `import_service`: batch import XML FatturaPA → parse → create suppliers/legal entities/documents/lines/VAT/payments/delivery notes
- `document_service`: search/filter documents, review workflow, physical copy management, due date updates
- `payment_service`: manage `Payment` records, import bank PDFs, reconciliation logic
- `supplier_service`: supplier listings, statistics, account statements
- `category_service`: CRUD categories, assign to `invoice_lines`
- `scan_service`: filesystem management for physical copies, DDT PDFs, bank PDFs

### Parsers (`app/parsers/`)

- `fatturapa_parser.py`: parse FatturaPA XML/P7M → DTOs
  - Current: manual lxml parsing with namespace-agnostic XPath
  - DTOs: `InvoiceDTO`, `SupplierDTO`, `InvoiceLineDTO`, `VatSummaryDTO`, `PaymentDTO`, `DeliveryNoteDTO`, `LegalEntityDTO`
  - Supports `.xml` and `.p7m` (PKCS#7 signature extraction)
  - Roadmap: migrate to `xsdata` for type-safe schema-driven parsing (v2.0)

## Common Workflows

### Import FatturaPA Files
1. Place XML/P7M files in `data/fatture_xml/` (or path in `config.IMPORT_XML_FOLDER`)
2. Service scans folder → parses each file → creates `Supplier`, `LegalEntity`, `Document`, `InvoiceLine`, `VatSummary`, `Payment`, `DeliveryNote` (if deferred invoice)
3. Logs to `ImportLog`, moves processed files
4. Entry: `app/services/import_service.py` → `import_all_invoices()`

### Document Review
1. UI filters documents by status, supplier, legal entity, date range, amounts
2. User updates `doc_status`: `imported` → `verified`/`rejected`
3. User assigns categories to `invoice_lines`
4. User requests/uploads physical copy (tracked via `physical_copy_status`)

### Payment Scheduling
1. Initial `Payment` records created from XML `DettaglioPagamento` during import
2. User manages statuses: `unpaid` → `planned` → `pending` → `paid`
3. Bank PDFs uploaded → parsed → stored in `payment_documents`
4. User reconciles bank PDFs with `Payment` records (manual or assisted matching)

## Database Schema (MySQL 8.x)

**Core Tables:**
- `documents` (supertype with discriminator `document_type`)
- `invoice_lines`, `vat_summaries` (invoice details)
- `payments` (deadlines for ALL document types)
- `payment_documents`, `payment_document_links` (bank PDFs + reconciliation)
- `delivery_notes` (DDT tracking)
- `suppliers`, `legal_entities` (registries)
- `categories`, `notes`, `import_logs`, `app_settings`, `users`
- `rent_contracts` (generates monthly `documents` with `document_type='rent'`)

**Indexes:**
- Compound: `(supplier_id, document_date DESC)`, `(legal_entity_id, document_date DESC)`, `(doc_status, document_date DESC)`, `(document_type, document_date DESC)`
- Single: all FKs, status fields, dates

**Constraints:**
- CHECK constraints on enums (`document_type`, `doc_status`, `physical_copy_status`, payment `status`, etc.)
- UNIQUE on `suppliers.vat_number`, `legal_entities.vat_number`, `categories.name`, `users.username`, etc.
- Conditional CHECK constraints (e.g., `invoice_type` NOT NULL only if `document_type='invoice'`)

## Development Conventions

**Data Access Rules:**
1. NEVER use raw `db.session` queries in routes/services
2. ALWAYS use repositories from `app/repositories/`
3. ALWAYS use `UnitOfWork` for multi-repository transactions
4. Repositories return ORM models; services return DTOs or models

**Adding New Document Types:**
1. Add value to `documents.document_type` CHECK constraint
2. Add nullable type-specific columns to `documents` table
3. Add conditional CHECK constraint for required fields
4. Update `Document` model with helper properties (`is_<type>`)
5. Optionally create specialized detail table (like `invoice_lines`)
6. Extend services/parsers as needed
7. No refactor needed: payments, notes, import_logs work automatically

**Code Style:**
- Follow existing patterns in each layer
- Keep services thin: delegate queries to repositories
- DTOs for parsing layer; ORM models everywhere else
- Logging: use app.logger (JSON format, rotating file handler)
- Templates: Jinja2 with Bootstrap-based UI

**Field Name Mapping (Common Pitfall):**
- Payment model uses: `due_date`, `expected_amount`, `notes`
- Legacy/external services may send: `payment_date`, `amount`, `description`
- ALWAYS map input to correct model fields

**Physical Copy Paths:**
- Use `app/services/scan_service.py` for file operations
- Paths stored relative to `config.UPLOAD_FOLDER` (default: `storage/`)
- Path in DB: `documents.physical_copy_file_path`

## Configuration & Storage

**Config (`config.py`):**
- `SQLALCHEMY_DATABASE_URI`: MySQL connection string
- `IMPORT_XML_FOLDER`: XML source directory (default: `data/fatture_xml/`)
- `UPLOAD_FOLDER`: storage root (default: `storage/`)
- `LOG_DIR`: logs directory (default: `logs/`)
- `LOG_LEVEL`: `DEBUG` (dev) / `INFO` (prod)

**Storage Directories:**
- `data/fatture_xml/`: XML/P7M import inbox
- `storage/`: physical copies, DDT PDFs, bank PDFs
- `logs/`: JSON logs (rotating)

## Known Issues & Gotchas

1. **Encoding for P7M/XML**: parser uses fallback encodings; malformed XML uses lxml recover mode
2. **Supplier/Legal Entity Uniqueness**: VAT/fiscal codes must be unique; import service creates if missing
3. **Payment Status Transitions**: respect enum values; don't skip states arbitrarily
4. **Delivery Note Matching**: deferred invoices create `xml_expected` DDT records; PDF inbox creates `pdf_import` records; matching logic differs
5. **Do NOT alter logging setup**: JSON format with RotatingFileHandler is production requirement
6. **Category Assignments**: use `category_service` methods; avoid direct `invoice_lines.category_id` updates
7. **Payment Reconciliation**: use `payment_document_links` for M:N; don't add ad-hoc joins
8. **Document Type Compatibility**: adding new types requires schema migration + CHECK constraint updates

## Testing & Validation

**Smoke Tests (Manual):**
1. Start server: `python manage.py runserver`
2. Import XML: verify import route works, check logs
3. Review documents: filter/search, status updates
4. Payment scheduling: create/update payments, upload bank PDFs

**Pre-Merge Checklist:**
- [ ] Server starts without errors
- [ ] No SQLAlchemy warnings in logs
- [ ] Import flow works (if touched)
- [ ] Review flow works (if touched)
- [ ] Payment flow works (if touched)

**TODO:** Add automated tests (pytest + fixtures)

## Future Roadmap

**Near-term:**
- Implement F24, insurance, MAV/CBILL, rent, receipt, tax document flows
- Extend parsers for non-FatturaPA formats (PDF extraction, OCR)
- Automate delivery note matching
- Automate payment reconciliation

**Technical Debt:**
- Migrate FatturaPA parser from lxml to `xsdata` (v2.0) for schema-driven type safety
- Add unit tests (repositories, services, parsers)
- Improve UX for review/scheduling (bulk actions, shortcuts)

## Documentation References

- **Architecture**: `docs/architecture.md` (layers, patterns, domain model)
- **Database**: `docs/database.md` (schema, indexes, constraints, queries)
- **LLM Context**: `docs/CONTEXT_FOR_LLM.md` (compact reference for AI assistants)
- **Index**: `docs/00_INDEX.md` (documentation entrypoint)
- **P7M Troubleshooting**: `docs/guides/p7m_troubleshooting.md`
- **Future Types**: `docs/roadmap/future_types.md`

## Git Workflow

**Branches:**
- `main`: stable development branch (default)
- Feature branches: create from `main`, PR back to `main`

**Commit Conventions:**
- Prefix: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`
- Keep commits atomic and descriptive
- Reference issues/PRs where applicable

**Never force-push to `main`**
