# CLAUDE.md - AI Assistant Guide for Gestionale Acquisti

> Comprehensive documentation for AI assistants working on this Flask-based invoice management system.

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture & Structure](#architecture--structure)
3. [Technology Stack](#technology-stack)
4. [Development Patterns](#development-patterns)
5. [Database & Models](#database--models)
6. [Key Modules](#key-modules)
7. [Development Workflows](#development-workflows)
8. [Coding Standards](#coding-standards)
9. [Testing & Verification](#testing--verification)
10. [Common Tasks](#common-tasks)
11. [Troubleshooting](#troubleshooting)
12. [AI Assistant Guidelines](#ai-assistant-guidelines)

---

## Project Overview

**Gestionale Acquisti** is a monolithic Flask web application for managing purchase invoices with XML import capabilities from Italian FatturaPA format.

### Purpose
- Import and parse Italian electronic invoices (FatturaPA XML format)
- Manage suppliers, invoices, invoice lines, and payments
- Categorize expenses for accounting purposes
- Track invoice verification workflow and payment status
- Export data for accounting systems

### Key Features
- **XML Import**: Parse FatturaPA XML files and store structured invoice data
- **Invoice Management**: Full CRUD operations with status tracking
- **Category Assignment**: Assign accounting categories to invoice lines
- **Payment Tracking**: Monitor payment status and due dates
- **Supplier Management**: Maintain supplier database with automatic creation from XML
- **Multi-Entity Support**: Handle invoices for multiple legal entities
- **Export**: Generate CSV exports for external systems
- **Web UI**: Full-featured web interface with HTML templates
- **REST API**: JSON endpoints for programmatic access

---

## Architecture & Structure

### Layered Architecture

The application follows a **clean layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────┐
│         Presentation Layer              │
│  ┌──────────────┐    ┌──────────────┐  │
│  │  Web Routes  │    │  API Routes  │  │
│  │  (HTML/UI)   │    │    (JSON)    │  │
│  └──────────────┘    └──────────────┘  │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Business Logic Layer            │
│           ┌──────────────┐              │
│           │   Services   │              │
│           │ (Use Cases)  │              │
│           └──────────────┘              │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│         Data Access Layer               │
│         ┌──────────────┐                │
│         │ Repositories │                │
│         │  (Queries)   │                │
│         └──────────────┘                │
└─────────────────────────────────────────┘
                  │
┌─────────────────────────────────────────┐
│            Domain Layer                 │
│          ┌──────────────┐               │
│          │    Models    │               │
│          │ (Entities)   │               │
│          └──────────────┘               │
└─────────────────────────────────────────┘
```

### Directory Structure

```
Progetto_Database_Acquisti/
├── app/                          # Main application package
│   ├── __init__.py              # App factory (create_app)
│   ├── extensions.py            # Shared extensions (db, logging)
│   │
│   ├── models/                  # Domain models (SQLAlchemy entities)
│   │   ├── invoice.py          # Invoice entity
│   │   ├── invoice_line.py     # Invoice line items
│   │   ├── supplier.py         # Supplier entity
│   │   ├── category.py         # Expense categories
│   │   ├── payment.py          # Payment records
│   │   ├── legal_entity.py     # Company/entity receiving invoice
│   │   ├── vat_summary.py      # VAT summary per rate
│   │   ├── import_log.py       # Import operation logs
│   │   ├── note.py             # Invoice notes
│   │   ├── app_setting.py      # Application settings
│   │   └── user.py             # User model (stub)
│   │
│   ├── repositories/            # Data access layer
│   │   ├── invoice_repository.py      # Invoice queries
│   │   ├── invoice_repo.py            # (Deprecated, use above)
│   │   ├── invoice_line_repo.py       # Line item queries
│   │   ├── supplier_repo.py           # Supplier queries
│   │   ├── category_repo.py           # Category queries
│   │   ├── payment_repo.py            # Payment queries
│   │   ├── legal_entity_repo.py       # Legal entity queries
│   │   ├── vat_summary_repo.py        # VAT summary queries
│   │   ├── import_log_repo.py         # Import log queries
│   │   └── notes_repo.py              # Notes queries
│   │
│   ├── services/                # Business logic layer
│   │   ├── invoice_service.py         # Invoice operations
│   │   ├── import_service.py          # XML import logic
│   │   ├── category_service.py        # Category management
│   │   ├── supplier_service.py        # Supplier operations
│   │   ├── payment_service.py         # Payment operations
│   │   ├── scan_service.py            # File scanning
│   │   ├── settings_service.py        # App settings
│   │   ├── unit_of_work.py            # Transaction management
│   │   ├── logging.py                 # Structured logging
│   │   └── dto/                       # Data Transfer Objects
│   │       └── invoice_filters.py     # Search filter DTOs
│   │
│   ├── parsers/                 # External data parsers
│   │   └── fatturapa_parser.py       # FatturaPA XML parser
│   │
│   ├── web/                     # Web UI routes (HTML)
│   │   ├── routes_main.py            # Dashboard
│   │   ├── routes_invoices.py        # Invoice pages
│   │   ├── routes_suppliers.py       # Supplier pages
│   │   ├── routes_categories.py      # Category pages
│   │   ├── routes_import.py          # Import UI
│   │   ├── routes_export.py          # Export UI
│   │   ├── routes_payments.py        # Payment pages
│   │   └── routes_settings.py        # Settings pages
│   │
│   ├── api/                     # REST API routes (JSON)
│   │   ├── api_invoices.py           # Invoice API
│   │   └── api_categories.py         # Category API
│   │
│   ├── middleware/              # HTTP middleware
│   │   └── auth_stub.py              # Authentication stub
│   │
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html                 # Base template
│   │   ├── dashboard.html            # Dashboard
│   │   ├── invoices/                 # Invoice templates
│   │   ├── suppliers/                # Supplier templates
│   │   ├── categories/               # Category templates
│   │   ├── import/                   # Import templates
│   │   ├── export/                   # Export templates
│   │   ├── payments/                 # Payment templates
│   │   └── settings/                 # Settings templates
│   │
│   └── static/                  # Static assets
│       ├── css/                      # Stylesheets
│       │   ├── main.css
│       │   ├── forms.css
│       │   └── tables.css
│       └── js/                       # JavaScript
│           ├── main.js
│           ├── filters.js
│           ├── invoices_list.js
│           └── categories_assign.js
│
├── logs/                        # Application logs (JSON format)
├── data/                        # Data directory
│   └── fatture_xml/            # XML import folder
│
├── config.py                    # Configuration classes
├── manage.py                    # CLI management script
├── run_app.py                   # Alternative app runner
├── requirements.txt             # Python dependencies
├── README.txt                   # Setup instructions
├── AGENTS.md                    # Agent guidelines (legacy)
├── db_commit_audit.md          # UnitOfWork refactoring guide
└── CLAUDE.md                    # This file
```

---

## Technology Stack

### Core Framework & Database
- **Flask 3.0+**: Web framework
- **Flask-SQLAlchemy 3.1+**: ORM and database toolkit
- **PyMySQL 1.1+**: MySQL database driver
- **MySQL 8.x**: Relational database

### Parsing & Data Processing
- **lxml 5.2+**: XML parsing for FatturaPA files
- **cryptography**: Security utilities

### Configuration & Environment
- **python-dotenv 1.0+**: Environment variable management

### Language Version
- **Python 3.10+** (tested with 3.12)

---

## Development Patterns

### 1. Unit of Work Pattern

The codebase uses the **Unit of Work pattern** for transaction management. This ensures automatic commit/rollback behavior.

**Location**: `app/services/unit_of_work.py`

**Usage**:
```python
from app.services.unit_of_work import UnitOfWork

def my_service_function():
    with UnitOfWork() as session:
        # Perform database operations
        obj = MyModel(name="example")
        session.add(obj)
        # Automatic commit on success
        # Automatic rollback on exception
```

**Key Points**:
- ALWAYS use `UnitOfWork()` for service-layer operations
- NEVER call `db.session.commit()` directly in service methods
- The context manager handles commit/rollback automatically
- See `db_commit_audit.md` for migration examples

### 2. Repository Pattern

Repositories encapsulate database queries and provide a clean interface for data access.

**Key Principles**:
- Repositories contain ONLY query logic (no business logic)
- Use SQLAlchemy query API
- Return domain models or None
- Accept optional `session` parameter for UnitOfWork integration

**Example**:
```python
# app/repositories/invoice_repository.py
def get_invoice_by_id(invoice_id: int, session=None) -> Optional[Invoice]:
    """Fetch invoice by ID."""
    if session is None:
        session = db.session
    return session.query(Invoice).filter_by(id=invoice_id).first()
```

### 3. Service Pattern

Services contain business logic and orchestrate repositories and models.

**Key Principles**:
- Services implement use cases
- Wrap operations in `UnitOfWork()` context
- Use repositories for data access
- Return domain models or DTOs
- Handle exceptions appropriately

**Example**:
```python
# app/services/invoice_service.py
def update_invoice_status(invoice_id: int, doc_status: str) -> Optional[Invoice]:
    with UnitOfWork() as session:
        invoice = get_invoice_by_id(invoice_id, session=session)
        if invoice is None:
            return None
        invoice.doc_status = doc_status
        return invoice
```

### 4. DTO Pattern

Data Transfer Objects are used for complex data structures, especially in parsers.

**Example**:
```python
# app/parsers/fatturapa_parser.py
@dataclass
class InvoiceDTO:
    header: Dict[str, Any]
    supplier: SupplierDTO
    lines: List[InvoiceLineDTO]
    vat_summaries: List[VatSummaryDTO]
```

### 5. Blueprint Pattern

Flask blueprints organize routes into logical modules.

**Blueprints**:
- **Web Blueprints** (return HTML): `main_bp`, `invoices_bp`, `suppliers_bp`, `categories_bp`, `import_bp`, `export_bp`, `settings_bp`, `payments_bp`
- **API Blueprints** (return JSON): `api_invoices_bp`, `api_categories_bp`

### 6. Factory Pattern

The app uses the factory pattern for initialization.

**App Factory**: `app/__init__.py::create_app()`

```python
from app import create_app
from config import DevConfig

app = create_app(DevConfig)
```

---

## Database & Models

### Entity Relationship Overview

```
┌─────────────────┐
│  LegalEntity    │
│  (Companies)    │
└────────┬────────┘
         │
         │ 1:N
         │
┌────────▼────────┐      N:1      ┌──────────────┐
│    Invoice      │◄───────────────┤   Supplier   │
│                 │                └──────────────┘
└────────┬────────┘
         │ 1:N
         │
         ├──────────────┬──────────────┬──────────────┬──────────────┐
         │              │              │              │              │
         ▼              ▼              ▼              ▼              ▼
┌────────────┐  ┌─────────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐
│InvoiceLine │  │ VatSummary  │  │ Payment  │  │  Note   │  │ImportLog │
│            │  │             │  │          │  │         │  │          │
└────┬───────┘  └─────────────┘  └──────────┘  └─────────┘  └──────────┘
     │
     │ N:1
     │
     ▼
┌────────────┐
│  Category  │
│ (Expenses) │
└────────────┘
```

### Core Models

#### Invoice (`app/models/invoice.py`)
Main invoice entity storing header-level information.

**Key Fields**:
- `supplier_id`: FK to Supplier
- `legal_entity_id`: FK to LegalEntity
- `invoice_number`, `invoice_series`, `invoice_date`: Document identification
- `registration_date`: Accounting registration date
- `total_taxable_amount`, `total_vat_amount`, `total_gross_amount`: Financial totals
- `doc_status`: Workflow status (imported, pending_physical_copy, verified, rejected, archived)
- `payment_status`: Payment status (unpaid, partially_paid, paid, overdue)
- `physical_copy_received`: Boolean flag
- `file_name`, `file_hash`: Original XML file tracking

**Status Values**:
- **doc_status**: `imported`, `pending_physical_copy`, `verified`, `rejected`, `archived`
- **payment_status**: `unpaid`, `partially_paid`, `paid`, `overdue`

#### InvoiceLine (`app/models/invoice_line.py`)
Individual line items within an invoice.

**Key Fields**:
- `invoice_id`: FK to Invoice
- `category_id`: FK to Category (nullable, assigned manually)
- `line_number`: Position in invoice
- `description`: Line item description
- `quantity`, `unit_price`: Quantities
- `taxable_amount`, `vat_rate`, `vat_amount`: Tax calculation

#### Supplier (`app/models/supplier.py`)
Vendor/supplier information.

**Key Fields**:
- `name`: Company name
- `vat_number`, `tax_code`: Tax identifiers
- `sdi_code`: Italian SDI code
- `address`, `postal_code`, `city`, `province`, `country`: Location

#### Category (`app/models/category.py`)
Expense categories for accounting classification.

**Key Fields**:
- `name`: Category name (unique)
- `description`: Category description
- `is_active`: Soft delete flag

#### Payment (`app/models/payment.py`)
Payment records linked to invoices.

**Key Fields**:
- `invoice_id`: FK to Invoice
- `payment_date`: Date of payment
- `amount`: Payment amount
- `payment_method`: Method (bank_transfer, cash, check, etc.)

#### LegalEntity (`app/models/legal_entity.py`)
Companies or individuals receiving invoices.

**Key Fields**:
- `name`: Entity name
- `vat_number`, `tax_code`: Tax identifiers
- `is_default`: Default entity flag

#### VatSummary (`app/models/vat_summary.py`)
VAT breakdown per rate (from XML DatiRiepilogo).

**Key Fields**:
- `invoice_id`: FK to Invoice
- `vat_rate`: Tax rate percentage
- `taxable_amount`, `vat_amount`: Amounts per rate

#### ImportLog (`app/models/import_log.py`)
Tracks XML import operations for auditing.

**Key Fields**:
- `invoice_id`: FK to Invoice (nullable if import failed)
- `file_name`, `file_hash`: File identification
- `status`: Import status (success, skipped, error)
- `message`: Import result message

---

## Key Modules

### FatturaPA Parser (`app/parsers/fatturapa_parser.py`)

Parses Italian electronic invoice XML files into structured DTOs.

**Main Function**:
```python
parse_invoice_xml(xml_path: Path) -> InvoiceDTO
```

**Key Features**:
- Namespace-agnostic XPath queries
- Tolerant to missing fields
- Returns structured DTOs
- Computes file hash for deduplication
- Extracts: supplier, invoice header, lines, VAT summaries, payment terms

**XML Structure** (FatturaPA 1.2):
- `FatturaElettronicaHeader/CedentePrestatore`: Supplier data
- `FatturaElettronicaBody/DatiGenerali`: Invoice header
- `FatturaElettronicaBody/DatiBeniServizi/DettaglioLinee`: Line items
- `FatturaElettronicaBody/DatiBeniServizi/DatiRiepilogo`: VAT summary
- `FatturaElettronicaBody/DatiPagamento`: Payment terms

### Import Service (`app/services/import_service.py`)

Orchestrates the XML import process.

**Main Function**:
```python
run_import(folder: Optional[str] = None, legal_entity_id: Optional[int] = None) -> Dict
```

**Import Flow**:
1. Scan folder for XML files
2. For each file:
   - Parse XML using `fatturapa_parser`
   - Check for duplicates (file_name, file_hash)
   - Get or create supplier
   - Create invoice tree (invoice + lines + VAT summaries)
   - Log import result
3. Return summary (success_count, skip_count, error_count)

**Deduplication**: Invoices are skipped if `file_name` or `file_hash` already exists.

**Transaction Management**: Each file import is wrapped in `UnitOfWork()`.

### Category Service (`app/services/category_service.py`)

Manages expense categories and category assignment to invoice lines.

**Key Functions**:
- `create_or_update_category()`: Upsert category
- `assign_category_to_line()`: Assign category to single line
- `bulk_assign_category_to_invoice_lines()`: Assign category to multiple lines

### Invoice Service (`app/services/invoice_service.py`)

Handles invoice search, detail retrieval, and status updates.

**Key Functions**:
- `search_invoices(filters: InvoiceSearchFilters)`: Search with filters
- `get_invoice_detail(invoice_id: int)`: Get full invoice with relationships
- `update_invoice_status()`: Update doc_status, payment_status, due_date
- `get_next_imported_invoice()`: Get next invoice in imported status

### Logging (`app/extensions.py` + `app/services/logging.py`)

**JSON Structured Logging**:
- All logs are output in JSON format
- File handler: Rotating log files (5MB max, 3 backups)
- Console handler: Stdout for container/dev environments
- Custom `JsonFormatter` class

**Log Fields**:
- `timestamp`: ISO 8601 UTC
- `level`: INFO, ERROR, DEBUG, etc.
- `logger`: Logger name
- `module`: Source module
- `message`: Log message
- `extra`: Custom fields

**Usage**:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Import completed", extra={"file_count": 10, "success": 8})
```

---

## Development Workflows

### Setup Workflow

1. **Clone Repository**
   ```bash
   git clone <repo-url>
   cd Progetto_Database_Acquisti
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # .venv\Scripts\activate   # Windows
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Database**
   - Update `config.py` with MySQL credentials
   - Or set environment variables:
     ```bash
     export DB_USER=ga_user
     export DB_PASSWORD=your_password
     export DB_HOST=localhost
     export DB_NAME=gestionale_acquisti
     ```

5. **Create Database Schema**
   ```bash
   python manage.py create-db
   ```

6. **Run Development Server**
   ```bash
   python manage.py runserver
   ```
   - Access at: `http://0.0.0.0:5000`
   - Health check: `http://0.0.0.0:5000/health`

### Import Workflow

1. **Place XML Files**
   - Default folder: `data/fatture_xml/`
   - Configure via `IMPORT_XML_FOLDER` in config

2. **Run Import**
   - Via Web UI: Navigate to `/import` and click "Avvia Import"
   - Via API: `POST /api/invoices/import`

3. **Review Results**
   - Check import logs in database (`import_logs` table)
   - Check application logs in `logs/app.log`
   - Review imported invoices at `/invoices`

4. **Verify Invoices**
   - Open invoice detail page
   - Assign categories to lines
   - Update document status
   - Record payments if needed

### Category Assignment Workflow

1. **Create Categories** (if not exist)
   - Navigate to `/categories`
   - Create expense categories

2. **Assign to Lines**
   - Option A: Single line assignment on invoice detail page
   - Option B: Bulk assignment via "Assegna Categoria" modal
   - Option C: API endpoint `POST /api/categories/{id}/assign`

### Git Workflow

**Branch Naming**:
- Feature branches: `claude/claude-md-<session-id>`
- All development on designated branch

**Commit Messages**:
- Italian or English
- Concise, descriptive
- Focus on "why" not "what"

**Push Commands**:
```bash
git push -u origin <branch-name>
```

---

## Coding Standards

### Language & Style

- **Python Version**: 3.10+ (tested with 3.12)
- **Language**: Python code; Italian comments and docstrings
- **Naming Conventions**:
  - Functions/variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Type Hints**: Use type hints where beneficial
- **Docstrings**: Italian, describe purpose and parameters

### Code Organization

- **Avoid Side Effects**: Models should be pure data structures
- **Single Responsibility**: Each function/class has one clear purpose
- **DRY Principle**: Don't repeat yourself; extract common logic

### Database Operations

- **ALWAYS use `UnitOfWork()`** for service-layer database operations
- **NEVER call `db.session.commit()`** directly in services
- **Repositories accept `session` parameter** for UnitOfWork integration
- **Avoid N+1 queries**: Use `joinedload()` or `selectinload()` for relationships

### Logging

- **Use JSON logger** from `app.extensions`
- **Include context**: Use `extra={}` for structured fields
- **Log levels**:
  - `DEBUG`: Detailed diagnostic info
  - `INFO`: Normal operations (import success, etc.)
  - `WARNING`: Unexpected but recoverable events
  - `ERROR`: Error conditions (import failures, etc.)

### Security

- **No hardcoded secrets**: Use environment variables
- **Validate inputs**: Especially file paths and user inputs
- **SQL Injection**: Use SQLAlchemy ORM (never raw SQL with string concatenation)
- **XSS Prevention**: Jinja2 auto-escapes; use `|safe` carefully

### Error Handling

- **Catch specific exceptions**: Avoid bare `except:`
- **Log errors with context**: Include relevant IDs, file names, etc.
- **Return appropriate responses**:
  - Web: Flash messages + redirect
  - API: JSON with error details and appropriate HTTP status

---

## Testing & Verification

### Manual Testing

**Verify Server Starts**:
```bash
python manage.py runserver
# Should start without errors
# Check logs/app.log for any issues
```

**Health Check**:
```bash
curl http://localhost:5000/health
# Expected: {"status": "ok"}
```

**Database Connection**:
```bash
python manage.py create-db
# Should complete without OperationalError
```

### Functional Testing

1. **Import Test**:
   - Place sample XML in `data/fatture_xml/`
   - Navigate to `/import`
   - Click "Avvia Import"
   - Check for success message
   - Verify invoice appears in `/invoices`

2. **Category Assignment Test**:
   - Open invoice detail
   - Assign category to a line
   - Verify assignment saved

3. **Payment Recording Test**:
   - Open invoice detail
   - Add payment record
   - Verify payment status updated

### Log Verification

Check `logs/app.log` for:
- No ERROR level logs during normal operation
- Proper JSON formatting
- Relevant context in `extra` fields

---

## Common Tasks

### Add New Model

1. Create model in `app/models/your_model.py`
2. Import in `app/models/__init__.py`
3. Create repository in `app/repositories/your_model_repo.py`
4. Run `python manage.py create-db` to create table

### Add New API Endpoint

1. Create route in `app/api/api_your_resource.py`
2. Register blueprint in `app/__init__.py::_register_blueprints()`
3. Follow pattern: use service layer, return JSON, handle errors

### Add New Web Page

1. Create route in `app/web/routes_your_page.py`
2. Create template in `app/templates/your_page/`
3. Register blueprint in `app/__init__.py`
4. Add navigation link in `app/templates/base.html`

### Migrate to UnitOfWork Pattern

See `db_commit_audit.md` for detailed examples. Pattern:

**Before**:
```python
def my_function():
    obj = MyModel()
    db.session.add(obj)
    db.session.commit()
```

**After**:
```python
def my_function():
    with UnitOfWork() as session:
        obj = MyModel()
        session.add(obj)
```

### Add New Configuration

1. Add to `config.py::Config` class
2. Use environment variable with default:
   ```python
   MY_SETTING = os.environ.get("MY_SETTING", "default_value")
   ```
3. Document in README.txt

### Debug Import Issues

1. Check XML file format (must be FatturaPA 1.2)
2. Check `import_logs` table for error messages
3. Review `logs/app.log` for detailed stacktraces
4. Verify supplier data is valid (required: name, vat_number or tax_code)
5. Check for duplicate file_name or file_hash

---

## Troubleshooting

### Database Connection Errors

**Symptom**: `OperationalError` when running server or create-db

**Solutions**:
1. Verify MySQL is running: `systemctl status mysql` or `brew services list`
2. Check credentials in `config.py` or environment variables
3. Ensure database exists: `CREATE DATABASE gestionale_acquisti;`
4. Verify user permissions: `GRANT ALL ON gestionale_acquisti.* TO 'ga_user'@'localhost';`

### Import Failures

**Symptom**: XML files not imported, errors in logs

**Solutions**:
1. Verify XML is valid FatturaPA format
2. Check file permissions (must be readable)
3. Ensure `IMPORT_XML_FOLDER` path exists and is correct
4. Check for required fields in XML (CedentePrestatore, DatiGenerali)
5. Review `import_logs` table for specific error messages

### Template Not Found

**Symptom**: `TemplateNotFound` error

**Solutions**:
1. Verify template exists in `app/templates/`
2. Check template path in `render_template()` call
3. Ensure Flask app created with correct `template_folder`

### Static Files Not Loading

**Symptom**: CSS/JS not loading, 404 errors

**Solutions**:
1. Verify files exist in `app/static/`
2. Use `url_for('static', filename='css/main.css')` in templates
3. Clear browser cache
4. Check Flask app created with correct `static_folder`

### JSON Logging Not Working

**Symptom**: Logs not in JSON format

**Solutions**:
1. Verify `init_extensions()` is called in app factory
2. Check `LOG_DIR` exists and is writable
3. Ensure no other logging config overrides JSON formatter

---

## AI Assistant Guidelines

### What to ALWAYS Do

1. **Read Before Writing**:
   - ALWAYS read files before modifying them
   - Understand existing code structure before proposing changes

2. **Use UnitOfWork Pattern**:
   - ALWAYS wrap service-layer DB operations in `with UnitOfWork() as session:`
   - NEVER call `db.session.commit()` directly

3. **Follow Architecture**:
   - Models: Pure data structures, no business logic
   - Repositories: Query logic only
   - Services: Business logic, use repositories
   - Routes: Request handling, call services

4. **Logging**:
   - Use JSON structured logging
   - Include relevant context in `extra={}`

5. **Error Handling**:
   - Catch specific exceptions
   - Log errors with context
   - Return appropriate responses

6. **Code Style**:
   - Italian comments and docstrings
   - snake_case for functions/variables
   - PascalCase for classes
   - Type hints where beneficial

### What to NEVER Do

1. **Configuration Changes**:
   - NEVER modify `config.py` without explicit user request
   - NEVER change database credentials

2. **Schema Changes**:
   - NEVER rename tables or columns without explicit approval
   - NEVER drop tables or columns

3. **Breaking Changes**:
   - NEVER rewrite importers without confirmation
   - NEVER remove or rename public APIs without discussion

4. **Direct DB Access**:
   - NEVER use `db.session.commit()` in services (use UnitOfWork)
   - NEVER write raw SQL queries (use SQLAlchemy ORM)

5. **Logging Changes**:
   - NEVER change JSON logging configuration
   - NEVER remove existing log statements

### Verification Checklist

Before completing any change, verify:

- [ ] Server starts without errors: `python manage.py runserver`
- [ ] No exceptions in logs
- [ ] Code follows architecture patterns
- [ ] UnitOfWork used for transactions
- [ ] Type hints present
- [ ] Italian docstrings added
- [ ] Error handling implemented
- [ ] Logging includes context

### Pull Request Format

Every PR should include:

1. **Summary**: Brief description of changes (2-3 sentences)
2. **Files Changed**: List of modified files with purpose
3. **Reasoning**: Why these changes were made
4. **Test Plan**: Steps to verify the changes work
   - [ ] Server starts successfully
   - [ ] Relevant functionality tested
   - [ ] No errors in logs

### Common Pitfalls

1. **Forgetting UnitOfWork**: Always wrap transactions
2. **Modifying wrong files**: Check file paths carefully
3. **Breaking existing functionality**: Test related features
4. **Ignoring deprecation warnings**: Use `invoice_repository.py` not `invoice_repo.py`
5. **Missing session parameter**: Repositories should accept `session=None`

### Helpful Context

- **Main entry point**: `app/__init__.py::create_app()`
- **Database instance**: `app.extensions.db`
- **CLI commands**: Defined in `manage.py`
- **Import folder**: Configured in `config.py::IMPORT_XML_FOLDER`
- **Log location**: `logs/app.log`

### When in Doubt

1. Check `AGENTS.md` for project-specific guidelines
2. Review `db_commit_audit.md` for UnitOfWork examples
3. Examine existing code for patterns
4. Ask user for clarification on ambiguous requirements

---

## Additional Resources

- **README.txt**: Setup and installation instructions
- **AGENTS.md**: Legacy agent guidelines (superseded by this file)
- **db_commit_audit.md**: UnitOfWork migration examples
- **config.py**: Configuration reference

---

**Last Updated**: 2025-12-05
**For**: AI Assistants (Claude, etc.)
**Maintainer**: Development Team
