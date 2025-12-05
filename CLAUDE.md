# CLAUDE.md - AI Assistant Guide for Gestionale Acquisti

> **Purpose**: This document provides AI assistants with comprehensive context about this codebase to enable effective collaboration on development tasks.

**Last Updated**: 2025-12-05

---

## 🎯 Project Overview

**Gestionale Acquisti** is a production-ready Flask web application for managing Italian procurement invoices with FatturaPA XML import capabilities.

### Key Capabilities
- Import and parse Italian FatturaPA electronic invoices (XML format)
- Complete invoice lifecycle management: import → review → approval → payment tracking
- Physical document tracking (request/receipt of paper copies)
- Payment document processing with invoice assignment
- Supplier and legal entity management
- Accounting categorization for invoice line items
- CSV export for reporting
- Structured JSON logging for monitoring

### Technology Stack
```
Backend:   Python 3.10+ • Flask 3.0+ • SQLAlchemy 3.1+ • MySQL 8.x
Parsing:   lxml 5.2+ (FatturaPA XML processing)
Frontend:  Jinja2 templates • HTML/CSS/JavaScript
Database:  MySQL 8.x with PyMySQL adapter
Config:    python-dotenv for environment management
Logging:   JSON-formatted structured logging with rotation
```

---

## 📁 Codebase Structure

### Directory Layout
```
Progetto_Database_Acquisti/
├── app/                              # Main application package
│   ├── __init__.py                   # App factory (create_app)
│   ├── extensions.py                 # SQLAlchemy, logging config
│   ├── models/                       # SQLAlchemy ORM models (11 models)
│   │   ├── invoice.py               # Core Invoice model
│   │   ├── invoice_line.py          # Invoice line items
│   │   ├── vat_summary.py           # VAT breakdown by rate
│   │   ├── payment.py               # Payment terms & records
│   │   ├── payment_document.py      # Payment proof documents
│   │   ├── note.py                  # Internal notes
│   │   ├── import_log.py            # Import audit trail
│   │   ├── supplier.py              # Vendor master data
│   │   ├── legal_entity.py          # Company/entity receiving invoices
│   │   ├── category.py              # Accounting categories
│   │   └── user.py                  # System users
│   ├── services/                     # Business logic layer
│   │   ├── unit_of_work.py          # Transaction management pattern
│   │   ├── import_service.py        # XML import orchestration
│   │   ├── invoice_service.py       # Invoice business logic
│   │   ├── payment_service.py       # Payment processing
│   │   ├── category_service.py      # Category operations
│   │   └── ...
│   ├── repositories/                 # Data access layer
│   │   ├── invoice_repository.py    # Invoice CRUD operations
│   │   ├── supplier_repository.py   # Supplier data access
│   │   └── ...
│   ├── web/                          # Web routes (HTML rendering)
│   │   ├── routes_invoices.py       # Invoice management routes
│   │   ├── routes_suppliers.py      # Supplier routes
│   │   ├── routes_import.py         # Import interface
│   │   ├── routes_export.py         # CSV export
│   │   ├── routes_payments.py       # Payment document routes
│   │   └── ...
│   ├── api/                          # REST API routes (JSON)
│   │   ├── api_invoices.py          # Invoice API endpoints
│   │   └── api_categories.py        # Category API
│   ├── parsers/                      # External format parsers
│   │   └── fatturapa_parser.py      # FatturaPA XML → DTO parser
│   ├── middleware/                   # Request/response processing
│   │   └── auth_stub.py             # Authentication stub (dev mode)
│   ├── templates/                    # Jinja2 HTML templates
│   │   ├── base.html                # Base template with nav
│   │   ├── invoices/                # Invoice-related templates
│   │   └── ...
│   └── static/                       # CSS, JavaScript, images
├── config.py                         # Configuration classes (Dev/Prod)
├── manage.py                         # CLI entry point (create-db, runserver)
├── run_app.py                        # Quick start script
├── requirements.txt                  # Python dependencies
├── README.txt                        # Setup instructions (Italian)
├── AGENTS.md                         # Developer guidelines
├── db_commit_audit.md               # Transaction refactoring notes
└── logs/                             # Application log files
```

### File Statistics
- **56 Python modules** across models, services, repositories, routes, and utilities
- **18 Jinja2 HTML templates** for web UI
- **11 SQLAlchemy models** representing the database schema

---

## 🏗️ Architecture Pattern

The application follows a **layered architecture** with clear separation of concerns:

```
HTTP Request
    ↓
┌─────────────────────────────────────────┐
│  Routes Layer (web/*, api/*)            │  ← HTTP handling, request validation
│  - Web routes return HTML (Jinja2)      │
│  - API routes return JSON                │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Services Layer (services/*)            │  ← Business logic orchestration
│  - Coordinates repositories & parsers    │
│  - Enforces business rules               │
│  - Manages transactions (UnitOfWork)     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Repositories Layer (repositories/*)    │  ← Data access abstraction
│  - CRUD operations                       │
│  - Query builders                        │
│  - No business logic                     │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Models Layer (models/*)                │  ← ORM definitions
│  - SQLAlchemy models                     │
│  - Relationships                          │
│  - No side effects                       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│  Database (MySQL)                       │  ← Persistent storage
└─────────────────────────────────────────┘
```

### Key Design Patterns

#### 1. App Factory Pattern (`app/__init__.py`)
```python
def create_app(config_class=None):
    """Create and configure Flask app"""
    app = Flask(__name__)
    app.config.from_object(config_class or DevConfig)

    # Initialize extensions
    db.init_app(app)

    # Register blueprints
    app.register_blueprint(invoices_bp)
    # ...

    return app
```

#### 2. Unit of Work Pattern (`services/unit_of_work.py`)
**CRITICAL**: Always use `UnitOfWork` context manager for transactions. Never call `db.session.commit()` directly.

```python
from app.services.unit_of_work import UnitOfWork

def some_service_function():
    with UnitOfWork() as session:
        # All database operations here
        invoice = get_invoice_by_id(123, session=session)
        invoice.status = "verified"
        # No explicit commit needed - automatic on context exit
    # Transaction committed automatically
```

**Benefits**:
- Automatic commit on success
- Automatic rollback on exceptions
- Clear transaction boundaries
- Consistent error handling

#### 3. Repository Pattern
Repositories encapsulate data access logic:

```python
# In repositories/invoice_repository.py
def get_invoice_by_id(invoice_id: int, session=None) -> Optional[Invoice]:
    """Fetch invoice by ID"""
    if session is None:
        session = db.session
    return session.query(Invoice).filter(Invoice.id == invoice_id).first()
```

#### 4. DTO Pattern (Data Transfer Objects)
Used in `parsers/fatturapa_parser.py` for XML parsing:

```python
@dataclass
class InvoiceDTO:
    supplier: SupplierDTO
    header: Dict[str, Any]
    lines: List[InvoiceLineDTO]
    vat_summaries: List[VatSummaryDTO]
    payments: List[PaymentDTO]
    file_hash: str
```

---

## 💾 Database Schema

### Core Entities & Relationships

```
┌──────────────┐         ┌──────────────┐
│ LegalEntity  │         │  Supplier    │
└──────┬───────┘         └──────┬───────┘
       │                        │
       │ 1:N                    │ 1:N
       │                        │
       └────────┐      ┌────────┘
                │      │
                ▼      ▼
          ┌──────────────┐
          │   Invoice    │  ← Central entity
          └──────┬───────┘
                 │ 1:N
                 ├─────────────────────────┐
                 │                         │
                 ▼                         ▼
        ┌──────────────┐          ┌──────────────┐
        │ InvoiceLine  │          │ VatSummary   │
        └──────┬───────┘          └──────────────┘
               │ N:1
               ▼
        ┌──────────────┐
        │  Category    │
        └──────────────┘

          Invoice
               │ 1:N
               ├─────────┬──────────┐
               ▼         ▼          ▼
           Payment    Note    ImportLog
               │
               │ N:1
               ▼
        PaymentDocument
```

### Key Models

#### Invoice (`invoices` table)
**Purpose**: Central entity for purchase invoices

**Key Fields**:
- `invoice_number`, `invoice_date` - Invoice identification
- `supplier_id` (FK) - Vendor reference
- `legal_entity_id` (FK) - Receiving company
- `total_taxable`, `total_vat`, `total_gross` - Financial amounts
- `doc_status` - Document lifecycle: `imported` | `pending_physical_copy` | `verified` | `rejected` | `archived`
- `payment_status` - Payment tracking: `unpaid` | `partial` | `paid`
- `due_date` - Payment due date
- `file_name`, `file_hash` - Source XML tracking
- `physical_copy_requested_at`, `physical_copy_received_at` - Physical document tracking

**Relationships**:
- `lines` (1:N) → InvoiceLine
- `vat_summaries` (1:N) → VatSummary
- `payments` (1:N) → Payment
- `notes` (1:N) → Note
- `supplier` (N:1) → Supplier
- `legal_entity` (N:1) → LegalEntity

#### InvoiceLine (`invoice_lines` table)
**Purpose**: Individual line items within invoices

**Key Fields**:
- `invoice_id` (FK) - Parent invoice
- `line_number` - Position in invoice
- `description` - Item description
- `quantity`, `unit_price` - Pricing
- `vat_rate`, `vat_amount` - Tax calculations
- `category_id` (FK) - Accounting category for reporting

#### Supplier (`suppliers` table)
**Purpose**: Vendor master data

**Key Fields**:
- `name` - Company name
- `vat_number`, `tax_code` - Italian tax identifiers
- `sdi_code` - Electronic invoicing code (Sistema di Interscambio)
- `address`, `city`, `postal_code`, `province`, `country`
- `is_active` - Soft delete flag

#### LegalEntity (`legal_entities` table)
**Purpose**: Companies/entities receiving invoices

**Key Fields**:
- `name` - Entity name
- `vat_number`, `fiscal_code` - Tax identifiers
- `address`, `city`, `postal_code`, `province`, `country`

#### Category (`categories` table)
**Purpose**: Accounting/cost categories for invoice lines

**Key Fields**:
- `name` - Category name
- `description` - Optional description
- `is_active` - Soft delete flag

#### Payment (`payments` table)
**Purpose**: Payment terms and actual payment records

**Key Fields**:
- `invoice_id` (FK) - Related invoice
- `payment_document_id` (FK) - Proof of payment
- `due_date`, `payment_date` - Timing
- `expected_amount`, `actual_amount` - Financial tracking

#### PaymentDocument (`payment_documents` table)
**Purpose**: Uploaded payment proof documents (bank statements, receipts)

**Key Fields**:
- `file_name`, `file_path` - Document storage
- `parsed_amount`, `parsed_date` - Extracted data (OCR/manual)
- `status` - Processing state: `pending_review` | `partially_assigned` | `error`

#### Note (`notes` table)
**Purpose**: Internal comments on invoices

**Key Fields**:
- `invoice_id` (FK) - Related invoice
- `user_id` (FK) - Author
- `note_text` - Content
- `created_at` - Timestamp

#### ImportLog (`import_logs` table)
**Purpose**: Audit trail for XML imports

**Key Fields**:
- `file_name`, `file_hash` - Source file tracking
- `status` - Import result: `success` | `skipped` | `error`
- `message` - Details/error messages
- `invoice_id` (FK) - Created invoice (if successful)
- `import_source` - Source folder path
- `imported_at` - Timestamp

---

## 🛣️ Routes & Endpoints

### Web Routes (HTML)

#### Invoice Management (`web/routes_invoices.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/invoices/` | GET | List all invoices with filters |
| `/invoices/to-review` | GET | Invoices awaiting review (imported status) |
| `/invoices/review/list` | GET | Dedicated review queue |
| `/invoices/review` | GET | Redirect to next invoice to review |
| `/invoices/review/<id>` | GET | Single invoice review form |
| `/invoices/<id>` | GET | Invoice detail view |
| `/invoices/<id>/preview` | GET | Invoice preview (iframe embed) |
| `/invoices/<id>/status` | POST | Update document/payment status |
| `/invoices/<id>/confirm` | POST | Confirm reviewed invoice → verified |
| `/invoices/<id>/reject` | POST | Reject reviewed invoice → rejected |
| `/invoices/physical-copies` | GET | Physical copy to-do list |
| `/invoices/<id>/physical-copy/request` | POST | Request physical copy from supplier |
| `/invoices/<id>/physical-copy/received` | POST | Mark physical copy as received |
| `/invoices/<id>/physical-copy/upload` | POST | Upload scanned physical copy |
| `/invoices/<id>/attach-scan` | GET/POST | Scan attachment interface |

#### Supplier Management (`web/routes_suppliers.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/suppliers/` | GET | List all suppliers with invoice statistics |
| `/suppliers/<id>` | GET | Supplier detail with related invoices |

#### Category Management (`web/routes_categories.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/categories/` | GET | List all accounting categories |
| `/categories/save` | POST | Create or update category |
| `/categories/bulk-assign/<invoice_id>` | GET | Bulk assignment UI for invoice lines |
| `/categories/bulk-assign/<invoice_id>` | POST | Execute bulk category assignment |

#### Import Interface (`web/routes_import.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/import/run` | GET | Import summary page |
| `/import/run` | POST | Execute FatturaPA XML import |

#### Export Interface (`web/routes_export.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/export/` | GET | Export options page |
| `/export/invoices` | GET | CSV export with date range filters |

#### Payment Document Processing (`web/routes_payments.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/payments/inbox` | GET | Payment document inbox |
| `/payments/upload` | POST | Upload payment proof documents |
| `/payments/<id>/review` | GET | Review payment document |
| `/payments/<id>/assign` | POST | Assign payment to invoices |
| `/payments/<id>/file` | GET | Download payment document file |

#### Settings (`web/routes_settings.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/settings/edit` | GET | Application settings editor |

### API Routes (JSON)

#### Invoice API (`api/api_invoices.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/api/invoices/<id>/status` | POST | Update invoice status (JSON response) |
| `/api/invoices/lines/<line_id>/category` | POST | Assign category to invoice line |

#### Category API (`api/api_categories.py`)
| Route | Method | Purpose |
|-------|--------|---------|
| Various | - | Category-related API endpoints |

### Health Check
| Route | Method | Purpose |
|-------|--------|---------|
| `/health` | GET | Returns `{"status": "ok"}` |

---

## ⚙️ Configuration

### Configuration Classes (`config.py`)

```python
class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    # Database connection
    DB_USER = os.getenv("DB_USER", "ga_user")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "gestionale_acquisti")
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("DATABASE_URL") or
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # Import settings
    IMPORT_XML_FOLDER = os.getenv("IMPORT_XML_FOLDER", "app/data/fatture_xml")

    # Logging
    LOG_DIR = os.getenv("LOG_DIR", "logs/")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE_NAME = os.getenv("LOG_FILE_NAME", "app.log")

class DevConfig(Config):
    """Development configuration"""
    DEBUG = True
    ENV = "development"
    LOG_LEVEL = "DEBUG"

class ProdConfig(Config):
    """Production configuration"""
    DEBUG = False
    ENV = "production"
    LOG_LEVEL = "INFO"
```

### Environment Variables

All configuration can be overridden via environment variables or `.env` file:

```bash
# Database
DB_USER=ga_user
DB_PASSWORD=secret
DB_HOST=localhost
DB_PORT=3306
DB_NAME=gestionale_acquisti
DATABASE_URL=mysql+pymysql://user:pass@host:port/dbname  # Override all DB settings

# Application
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# Import
IMPORT_XML_FOLDER=/path/to/xml/files

# Logging
LOG_DIR=logs/
LOG_LEVEL=DEBUG
LOG_FILE_NAME=app.log

# Flask run settings
FLASK_RUN_HOST=0.0.0.0
FLASK_RUN_PORT=5000
```

---

## 🔨 Development Workflow

### Setup & Installation

1. **Clone repository**:
   ```bash
   git clone <repository-url>
   cd Progetto_Database_Acquisti
   ```

2. **Create virtual environment** (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate    # Linux/macOS
   # .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database**:
   - Update `config.py` or create `.env` file with MySQL credentials
   - Ensure MySQL 8.x is running
   - Create database: `CREATE DATABASE gestionale_acquisti;`

5. **Create tables**:
   ```bash
   python manage.py create-db
   ```

6. **Run development server**:
   ```bash
   python manage.py runserver
   # Or: python run_app.py
   ```

7. **Verify installation**:
   - Server starts without errors on http://0.0.0.0:5000
   - No exceptions in console or `logs/app.log`
   - Health check: `curl http://localhost:5000/health` → `{"status": "ok"}`

### CLI Commands (`manage.py`)

```bash
# Create database tables
python manage.py create-db

# Run development server
python manage.py runserver

# Custom host/port
FLASK_RUN_HOST=127.0.0.1 FLASK_RUN_PORT=8000 python manage.py runserver
```

---

## 📝 Coding Standards & Conventions

### Language & Style

**CRITICAL**: All code comments, docstrings, and commit messages MUST be in **Italian**.

```python
# ✅ CORRECT
def calcola_totale_fattura(fattura_id: int) -> Decimal:
    """
    Calcola il totale lordo di una fattura sommando tutte le righe.

    Args:
        fattura_id: ID della fattura da calcolare

    Returns:
        Importo totale lordo (IVA inclusa)
    """
    # Recupera tutte le righe della fattura
    righe = get_righe_fattura(fattura_id)
    return sum(r.importo_lordo for r in righe)

# ❌ INCORRECT (English comments)
def calculate_invoice_total(invoice_id: int) -> Decimal:
    """Calculate the gross total of an invoice"""
    # Get all invoice lines
    lines = get_invoice_lines(invoice_id)
    return sum(l.gross_amount for l in lines)
```

### Naming Conventions

- **Functions/Variables**: `snake_case`
  ```python
  def get_invoice_by_id(invoice_id: int):
      total_amount = calculate_total()
  ```

- **Classes**: `PascalCase`
  ```python
  class InvoiceService:
      class InvoiceRepository:
  ```

- **Constants**: `UPPER_SNAKE_CASE`
  ```python
  MAX_IMPORT_FILES = 100
  DEFAULT_VAT_RATE = Decimal("22.0")
  ```

- **Private methods**: Prefix with single underscore
  ```python
  def _internal_helper_method():
      pass
  ```

### Model Conventions

**CRITICAL**: Models should be **data containers only** - no side effects, no business logic.

```python
# ✅ CORRECT - Model with no side effects
class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), nullable=False)
    total_gross = db.Column(db.Numeric(15, 2), nullable=False)

    # Relationships
    supplier = db.relationship("Supplier", back_populates="invoices")

# ❌ INCORRECT - Model with business logic
class Invoice(db.Model):
    def save(self):
        db.session.add(self)
        db.session.commit()  # Side effect!

    def calculate_total(self):
        # Business logic in model!
        return sum(line.amount for line in self.lines)
```

**Business logic belongs in services, not models.**

### Transaction Management

**CRITICAL**: Use `UnitOfWork` context manager for ALL database operations. **NEVER** call `db.session.commit()` directly.

```python
# ✅ CORRECT - Using UnitOfWork
from app.services.unit_of_work import UnitOfWork

def update_invoice_status(invoice_id: int, new_status: str):
    with UnitOfWork() as session:
        invoice = get_invoice_by_id(invoice_id, session=session)
        invoice.doc_status = new_status
        # Automatic commit on exit, rollback on exception

# ❌ INCORRECT - Direct commit
def update_invoice_status(invoice_id: int, new_status: str):
    invoice = get_invoice_by_id(invoice_id)
    invoice.doc_status = new_status
    db.session.commit()  # Don't do this!
```

**Why UnitOfWork?**
- Automatic commit on success
- Automatic rollback on exceptions
- Clear transaction boundaries
- Consistent error handling
- Easier testing

### Logging

**CRITICAL**: Use the application's JSON logger from `extensions.py`. Never print to console.

```python
# ✅ CORRECT - Using app logger
from app.extensions import get_logger

logger = get_logger(__name__)

def import_invoice(file_path: str):
    logger.info("Avvio import fattura", extra={"file": file_path})
    try:
        result = process_file(file_path)
        logger.info("Import completato", extra={"invoice_id": result.id})
    except Exception as e:
        logger.error("Errore durante import", extra={"error": str(e)})
        raise

# ❌ INCORRECT - Using print
def import_invoice(file_path: str):
    print(f"Importing {file_path}")  # Don't do this!
```

**Log Levels**:
- `DEBUG`: Detailed diagnostic information (development only)
- `INFO`: General informational messages (normal operations)
- `WARNING`: Warning messages (recoverable issues)
- `ERROR`: Error messages (failures)
- `CRITICAL`: Critical errors (system failures)

**Log Format** (JSON):
```json
{
  "timestamp": "2025-12-05T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.services.import_service",
  "module": "import_service",
  "message": "Import completato",
  "invoice_id": 123,
  "file": "/path/to/invoice.xml"
}
```

### Repository Pattern

Repositories handle data access, returning models or None:

```python
# ✅ CORRECT - Repository function
def get_invoice_by_id(invoice_id: int, session=None) -> Optional[Invoice]:
    """
    Recupera una fattura per ID.

    Args:
        invoice_id: ID della fattura
        session: Sessione SQLAlchemy opzionale (per UnitOfWork)

    Returns:
        Oggetto Invoice o None se non trovato
    """
    if session is None:
        session = db.session

    return session.query(Invoice).filter(Invoice.id == invoice_id).first()

# ❌ INCORRECT - Business logic in repository
def get_invoice_by_id(invoice_id: int) -> Optional[Invoice]:
    invoice = db.session.query(Invoice).first()
    if invoice:
        invoice.last_accessed = datetime.now()  # Business logic!
        db.session.commit()  # Transaction handling!
    return invoice
```

### Service Pattern

Services orchestrate business logic, using repositories and UnitOfWork:

```python
# ✅ CORRECT - Service function
def approve_invoice(invoice_id: int, user_id: int) -> Dict[str, Any]:
    """
    Approva una fattura dopo revisione.

    Args:
        invoice_id: ID della fattura da approvare
        user_id: ID dell'utente che approva

    Returns:
        Dizionario con esito operazione
    """
    with UnitOfWork() as session:
        # Recupera fattura
        invoice = get_invoice_by_id(invoice_id, session=session)
        if not invoice:
            return {"success": False, "message": "Fattura non trovata"}

        # Verifica stato
        if invoice.doc_status != "imported":
            return {"success": False, "message": "Fattura non in stato revisione"}

        # Aggiorna stato
        invoice.doc_status = "verified"
        invoice.verified_at = datetime.now()
        invoice.verified_by = user_id

        # Crea nota di approvazione
        note = Note(
            invoice_id=invoice_id,
            user_id=user_id,
            note_text="Fattura approvata dopo revisione"
        )
        session.add(note)

        # Log operazione
        logger.info(
            "Fattura approvata",
            extra={"invoice_id": invoice_id, "user_id": user_id}
        )

        return {"success": True, "message": "Fattura approvata"}
```

---

## 🚫 Critical "Do Not" Rules

### Configuration Changes
❌ **NEVER modify `config.py` without explicit user request**
- Database connection parameters are environment-specific
- Changes can break deployments
- Use environment variables instead

### Database Schema Changes
❌ **NEVER rename tables or columns without explicit permission**
- Breaks existing data
- Requires migration planning
- Affects all deployment environments

### Import System
❌ **NEVER rewrite the FatturaPA importer without confirmation**
- Complex XML parsing logic
- Extensively tested with real data
- Multiple edge cases handled

### Direct Database Access
❌ **NEVER use `db.session.commit()` directly**
- Always use `UnitOfWork` context manager
- See "Transaction Management" section above

### Logging Configuration
❌ **NEVER modify logging setup in `extensions.py`**
- Structured JSON logging is production requirement
- Log rotation is configured for operations
- Changes affect monitoring/alerting

### Authentication
❌ **Current auth is stub only**
- `middleware/auth_stub.py` provides fake user for development
- Real authentication is planned but not yet implemented
- Do not assume `g.current_user` is secure

---

## 🧪 Testing & Verification

### Manual Verification Checklist

Since automated tests are not yet implemented, verify changes manually:

1. **Server starts successfully**:
   ```bash
   python manage.py runserver
   # Should start without exceptions
   ```

2. **No errors in logs**:
   ```bash
   tail -f logs/app.log
   # Should show INFO messages, no ERROR/EXCEPTION
   ```

3. **Health check responds**:
   ```bash
   curl http://localhost:5000/health
   # Should return: {"status": "ok"}
   ```

4. **Key routes accessible**:
   - `/` - Home/dashboard
   - `/invoices/` - Invoice list
   - `/suppliers/` - Supplier list
   - `/import/run` - Import interface

5. **Database operations work**:
   - Create test invoice
   - Update invoice status
   - Add invoice line
   - Verify transaction rollback on error

### Testing FatturaPA Import

Place XML files in `app/data/fatture_xml/` (or configured folder) and test:

```bash
# Via web interface
# Navigate to /import/run and click "Esegui Import"

# Check logs for import results
tail -f logs/app.log | grep "import"
```

**Validation**:
- ImportLog record created for each file
- Invoice created with correct data
- Supplier created/matched
- Invoice lines populated
- VAT summaries calculated
- No duplicate imports (file_hash check)

---

## 📊 Common Development Tasks

### Adding a New Route

1. **Determine type**: Web (HTML) or API (JSON)?

2. **Create route in appropriate module**:
   ```python
   # In app/web/routes_invoices.py (for web routes)

   @invoices_bp.route("/invoices/<int:invoice_id>/archive", methods=["POST"])
   def archive_invoice(invoice_id):
       """Archivia una fattura"""
       # Usa il service layer
       result = invoice_service.archive_invoice(invoice_id)

       if result["success"]:
           flash("Fattura archiviata con successo", "success")
       else:
           flash(result["message"], "error")

       return redirect(url_for("invoices.invoice_detail", id=invoice_id))
   ```

3. **Implement business logic in service**:
   ```python
   # In app/services/invoice_service.py

   def archive_invoice(invoice_id: int) -> Dict[str, Any]:
       """
       Archivia una fattura verificata.

       Args:
           invoice_id: ID della fattura da archiviare

       Returns:
           Dizionario con esito operazione
       """
       with UnitOfWork() as session:
           invoice = get_invoice_by_id(invoice_id, session=session)

           if not invoice:
               return {"success": False, "message": "Fattura non trovata"}

           if invoice.doc_status != "verified":
               return {
                   "success": False,
                   "message": "Solo fatture verificate possono essere archiviate"
               }

           invoice.doc_status = "archived"
           invoice.archived_at = datetime.now()

           logger.info("Fattura archiviata", extra={"invoice_id": invoice_id})

           return {"success": True, "message": "Fattura archiviata"}
   ```

4. **Test manually** (see Testing section)

### Adding a New Model Field

1. **Update model class**:
   ```python
   # In app/models/invoice.py

   class Invoice(db.Model):
       # ... existing fields ...

       # Nuovo campo
       archived_at = db.Column(db.DateTime, nullable=True)
       archived_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
   ```

2. **Drop and recreate database** (development only):
   ```bash
   # WARNING: This deletes all data!
   python manage.py create-db
   ```

3. **Or write migration script** (production):
   ```sql
   ALTER TABLE invoices
   ADD COLUMN archived_at DATETIME NULL,
   ADD COLUMN archived_by INT NULL,
   ADD FOREIGN KEY (archived_by) REFERENCES users(id);
   ```

4. **Update affected services/repositories** to handle new field

5. **Update templates** if field should be displayed

### Adding a New Service Function

1. **Identify correct service module** (or create new one)

2. **Implement with UnitOfWork**:
   ```python
   # In app/services/invoice_service.py

   def bulk_update_supplier(old_supplier_id: int, new_supplier_id: int) -> Dict[str, Any]:
       """
       Sposta tutte le fatture da un fornitore a un altro.

       Args:
           old_supplier_id: Fornitore da cui spostare
           new_supplier_id: Fornitore destinazione

       Returns:
           Dizionario con esito e conteggio fatture aggiornate
       """
       with UnitOfWork() as session:
           # Verifica esistenza fornitori
           old_supplier = get_supplier_by_id(old_supplier_id, session=session)
           new_supplier = get_supplier_by_id(new_supplier_id, session=session)

           if not old_supplier or not new_supplier:
               return {"success": False, "message": "Fornitore non trovato"}

           # Recupera tutte le fatture
           invoices = list_invoices_by_supplier(old_supplier_id, session=session)

           # Aggiorna fornitore
           for invoice in invoices:
               invoice.supplier_id = new_supplier_id

           logger.info(
               "Fatture spostate tra fornitori",
               extra={
                   "from_supplier": old_supplier_id,
                   "to_supplier": new_supplier_id,
                   "count": len(invoices)
               }
           )

           return {
               "success": True,
               "message": f"{len(invoices)} fatture aggiornate",
               "count": len(invoices)
           }
   ```

3. **Use in route handler**

4. **Test manually**

### Debugging Import Issues

1. **Check logs**:
   ```bash
   tail -f logs/app.log | grep -i "import\|error\|exception"
   ```

2. **Verify XML file structure**:
   - Must be valid FatturaPA format
   - Namespace-independent XPath used (tolerant parsing)

3. **Check ImportLog table**:
   ```sql
   SELECT * FROM import_logs
   ORDER BY imported_at DESC
   LIMIT 10;
   ```

4. **Common issues**:
   - Missing required fields → Check XML has `CedentePrestatore`, `DatiGenerali`, etc.
   - Duplicate import → Check `file_hash` collision in invoices table
   - Supplier creation fails → Check VAT number format
   - Legal entity missing → Provide `legal_entity_id` parameter

5. **Test XML parsing in isolation**:
   ```python
   from app.parsers.fatturapa_parser import parse_fatturapa

   xml_path = "app/data/fatture_xml/test_invoice.xml"
   dto = parse_fatturapa(xml_path)
   print(dto)
   ```

---

## 🔐 Security Considerations

### Current State
⚠️ **Authentication is STUB only** (`middleware/auth_stub.py`)
- Provides fake user for development: `g.current_user`
- **Not secure for production**
- Real authentication system planned but not implemented

### When Implementing Auth
- Replace stub middleware with real authentication
- Implement password hashing (use `werkzeug.security`)
- Add role-based access control (User.role: admin/user/readonly)
- Protect sensitive routes with login required decorators
- Implement CSRF protection for forms

### Input Validation
- ✅ SQLAlchemy ORM provides SQL injection protection
- ⚠️ Validate file uploads (size, type, malware scanning)
- ⚠️ Sanitize HTML in note text (XSS prevention)
- ✅ Use parameterized queries (already done via ORM)

### File Handling
- XML imports from trusted folder only (configured path)
- Payment documents uploaded to secure location
- Validate file extensions and MIME types
- Implement file size limits

---

## 🔄 Git Workflow

### Branch Naming
Current convention based on recent commits:
```
codex/[feature-name]
claude/[branch-name]
```

Examples:
- `codex/verify-flask-route-for-review_loop`
- `codex/update-invoice-review-template`

### Commit Messages
Use clear, descriptive Italian commit messages:

```bash
# ✅ Good commit messages
git commit -m "Aggiungi validazione stato fattura prima dell'approvazione"
git commit -m "Correggi calcolo IVA per aliquote multiple"
git commit -m "Implementa archiviazione fatture verificate"

# ❌ Poor commit messages
git commit -m "fix"
git commit -m "update"
git commit -m "wip"
```

### Pull Request Format
Every PR should include:

1. **Summary**: What does this PR do?
2. **Files changed**: List of modified files
3. **Reasoning**: Why was this change needed?
4. **Steps to test**: How to verify the changes work

Example:
```markdown
## Summary
Implementa la funzionalità di archiviazione per fatture verificate.

## Files changed
- app/models/invoice.py (aggiunti campi archived_at, archived_by)
- app/services/invoice_service.py (aggiunta funzione archive_invoice)
- app/web/routes_invoices.py (aggiunta route /invoices/<id>/archive)
- app/templates/invoices/detail.html (aggiunto pulsante archivia)

## Reasoning
Le fatture verificate necessitano di un'ulteriore fase di archiviazione dopo
la verifica per mantenere pulita la vista principale.

## Steps to test
1. Avvia il server: `python manage.py runserver`
2. Crea una fattura di test e portala in stato "verified"
3. Naviga su /invoices/<id>
4. Clicca "Archivia"
5. Verifica che lo stato passi ad "archived"
6. Verifica che archived_at sia popolato
```

---

## 📚 Key Files Reference

### Entry Points
- `manage.py` - CLI tool (create-db, runserver)
- `run_app.py` - Quick start script
- `app/__init__.py` - App factory

### Configuration
- `config.py` - Configuration classes
- `.env` - Environment variables (not in repo)

### Core Business Logic
- `app/services/import_service.py` - FatturaPA XML import orchestration
- `app/services/invoice_service.py` - Invoice lifecycle management
- `app/services/payment_service.py` - Payment processing
- `app/services/category_service.py` - Category assignment
- `app/services/unit_of_work.py` - Transaction management

### Data Access
- `app/repositories/invoice_repository.py` - Invoice CRUD
- `app/repositories/supplier_repository.py` - Supplier CRUD
- `app/repositories/category_repository.py` - Category CRUD
- `app/repositories/payment_repository.py` - Payment CRUD

### Models
- `app/models/invoice.py` - Central Invoice model
- `app/models/supplier.py` - Vendor model
- `app/models/legal_entity.py` - Receiving company model
- `app/models/category.py` - Accounting category model

### Parsing
- `app/parsers/fatturapa_parser.py` - FatturaPA XML → DTO parser

### Web Routes
- `app/web/routes_invoices.py` - Invoice management (413 lines)
- `app/web/routes_suppliers.py` - Supplier views
- `app/web/routes_import.py` - Import interface
- `app/web/routes_export.py` - CSV export
- `app/web/routes_payments.py` - Payment documents

### API Routes
- `app/api/api_invoices.py` - Invoice JSON API
- `app/api/api_categories.py` - Category JSON API

### Infrastructure
- `app/extensions.py` - SQLAlchemy, logging setup
- `app/middleware/auth_stub.py` - Auth stub (development)

---

## 🎓 Learning Resources

### Understanding FatturaPA
FatturaPA is Italy's mandatory electronic invoicing format for B2B and B2G transactions.

**Key Concepts**:
- **SDI (Sistema di Interscambio)**: Government interchange system
- **Cedente/Prestatore**: Supplier/service provider
- **Cessionario/Committente**: Customer/client
- **Codice Destinatario**: Recipient code (7-character SDI code)
- **Ritenuta**: Withholding tax
- **Bollo**: Stamp duty

**XML Structure**:
```xml
<FatturaElettronica>
  <FatturaElettronicaHeader>
    <CedentePrestatore>...</CedentePrestatore>
    <CessionarioCommittente>...</CessionarioCommittente>
  </FatturaElettronicaHeader>
  <FatturaElettronicaBody>
    <DatiGenerali>...</DatiGenerali>
    <DatiBeniServizi>...</DatiBeniServizi>
    <DatiPagamento>...</DatiPagamento>
  </FatturaElettronicaBody>
</FatturaElettronica>
```

### Italian Tax Identifiers
- **Partita IVA (VAT Number)**: 11-digit business tax ID
- **Codice Fiscale (Tax Code)**: 16-character personal tax ID (or 11-digit for companies)
- Both are mandatory for invoicing

---

## 🤖 AI Assistant Guidelines

### When Working on This Codebase

1. **Always read before editing**: Use Read tool to understand existing code before making changes

2. **Use Italian for code comments**: All comments, docstrings, and commit messages in Italian

3. **Follow transaction pattern**: Use `UnitOfWork` context manager, never direct commits

4. **Respect layering**:
   - Routes → Services → Repositories → Models
   - Business logic in services only
   - Models are data containers only

5. **Log appropriately**: Use JSON logger from extensions, never print statements

6. **Ask before major changes**:
   - Database schema modifications
   - Configuration changes
   - Import system rewrites
   - Authentication implementation

7. **Test manually**: Verify server starts, check logs, test affected routes

8. **Document changes**: Explain what, why, and how to test

### Common Pitfalls to Avoid

❌ Mixing English and Italian comments
❌ Calling `db.session.commit()` directly
❌ Putting business logic in models
❌ Using print() instead of logger
❌ Assuming authentication is secure (it's a stub!)
❌ Modifying config.py without asking
❌ Changing table/column names
❌ Forgetting to use UnitOfWork for transactions
❌ Not reading files before editing them

### Effective Collaboration

✅ Ask clarifying questions when requirements are unclear
✅ Explain reasoning in commit messages
✅ Provide testing steps for all changes
✅ Use structured logging with extra context
✅ Keep functions focused and testable
✅ Follow existing code patterns
✅ Reference documentation (this file!)

---

## 📞 Support & Questions

### Documentation Files
- `CLAUDE.md` (this file) - Comprehensive AI assistant guide
- `AGENTS.md` - Developer guidelines (Italian)
- `README.txt` - Setup instructions (Italian)
- `db_commit_audit.md` - Transaction refactoring notes

### Code Comments
Most functions have Italian docstrings explaining purpose, parameters, and return values.

### Asking Questions
When unclear about functionality:
1. Read relevant source files
2. Check logs for runtime behavior
3. Review related tests (when available)
4. Check git history for context
5. Ask user for clarification

---

## 📈 Future Enhancements (Planned)

Based on codebase structure, these are likely planned improvements:

- [ ] Real authentication system (replacing auth_stub)
- [ ] Automated testing (pytest, unittest)
- [ ] Database migrations (Alembic)
- [ ] API authentication (JWT tokens)
- [ ] Advanced reporting/analytics
- [ ] Email notifications
- [ ] Document OCR for payment matching
- [ ] Multi-currency support
- [ ] Audit trail for all changes
- [ ] Export to accounting software formats

---

## 🏁 Quick Reference Card

### Essential Commands
```bash
# Setup
pip install -r requirements.txt
python manage.py create-db

# Run
python manage.py runserver

# Logs
tail -f logs/app.log
```

### Essential Patterns
```python
# Transaction
with UnitOfWork() as session:
    invoice = get_invoice_by_id(123, session=session)
    invoice.status = "verified"

# Logging
logger.info("Operazione completata", extra={"invoice_id": 123})

# Repository
def get_entity(entity_id: int, session=None) -> Optional[Entity]:
    if session is None:
        session = db.session
    return session.query(Entity).filter(Entity.id == entity_id).first()
```

### File Locations
```
Routes:         app/web/routes_*.py, app/api/api_*.py
Services:       app/services/*_service.py
Repositories:   app/repositories/*_repository.py
Models:         app/models/*.py
Templates:      app/templates/
Config:         config.py
```

---

**Last Updated**: 2025-12-05
**Maintainer**: Project team
**AI Assistant Version**: Optimized for Claude Code assistants

---

*This document is designed to help AI assistants quickly understand and effectively work on the Gestionale Acquisti codebase. For questions or corrections, please update this file and commit changes.*
