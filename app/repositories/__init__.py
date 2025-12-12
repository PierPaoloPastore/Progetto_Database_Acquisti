"""
Pacchetto per i repository che incapsulano l'accesso ai dati.

La logica di business rimane nei servizi (app.services.*).
"""

from .supplier_repo import (
    get_supplier_by_id,
    get_supplier_by_vat_number,
    get_supplier_by_fiscal_code,
    list_suppliers,
    create_supplier,
    update_supplier,
    get_or_create_supplier_from_dto,
)
from .legal_entity_repo import list_legal_entities, get_legal_entity_by_id

# NUOVO REPOSITORY DOCUMENTI (Sostituisce invoice_repo)
from .document_repo import (
    get_document_by_id,
    get_document_by_file_name,
    get_document_by_file_hash,
    find_existing_document,
    search_documents,
    list_imported_documents,
    get_next_imported_document,
    create_document,
    update_document,
    create_document_from_fatturapa,
    list_accounting_years,
    get_supplier_account_balance,
    list_supplier_legal_entities,
)

from .document_line_repo import (
    get_document_line_by_id,
    list_lines_by_document,
    list_lines_by_category,
    create_document_line,
    update_document_line,
)
from .vat_summary_repo import (
    list_vat_summaries_by_invoice,
    create_vat_summary,
)
from .payment_repo import (
    get_payment_by_id,
    list_payments_by_invoice,
    list_overdue_payments,
    create_payment,
    update_payment,
    create_payment_document,
    get_payment_document,
    list_payment_documents_by_status,
    list_payments_for_invoice,
    sum_payments_for_invoice,
)
# app/repositories/__init__.py

# RIMUOVI o COMMENTA le vecchie importazioni di categoria:
# from .category_repo import (
#     get_category_by_id,
#     get_category_by_name,
#     list_categories,
#     list_active_categories,
#     create_category,
#     update_category,
# )

# AGGIUNGI la nuova classe
from .category_repo import CategoryRepository

# ... lascia invariati gli altri import (es. invoice_repo, supplier_repo, ecc.) ...
# Nota: Assicurati che document_line_repo e le altre funzioni che usi
# in category_service (es. get_document_line_by_id) siano ancora importate/esposte qui.
from .notes_repo import (
    get_note_by_id,
    list_notes_by_invoice,
    create_note,
)
from .import_log_repo import (
    get_import_log_by_id,
    list_import_logs,
    list_import_logs_by_file_name,
    get_import_log_by_file_hash,
    find_document_by_file_hash,
    create_import_log,
)

__all__ = [
    # Suppliers
    "get_supplier_by_id",
    "get_supplier_by_vat_number",
    "get_supplier_by_fiscal_code",
    "list_suppliers",
    "create_supplier",
    "update_supplier",
    "get_or_create_supplier_from_dto",
    # Legal entities
    "list_legal_entities",
    "get_legal_entity_by_id",
    # Documents (ex Invoices)
    "get_document_by_id",
    "get_document_by_file_name",
    "get_document_by_file_hash",
    "find_existing_document",
    "search_documents",
    "list_imported_documents",
    "get_next_imported_document",
    "create_document",
    "update_document",
    "create_document_from_fatturapa",
    "list_accounting_years",
    "get_supplier_account_balance",
    "list_supplier_legal_entities",
    # Document lines
    "list_lines_by_document",
    "list_lines_by_category",
    "create_document_line",
    "update_document_line",
    # VAT summaries
    "list_vat_summaries_by_invoice",
    "create_vat_summary",
    # Payments
    "get_payment_by_id",
    "list_payments_by_invoice",
    "list_overdue_payments",
    "create_payment",
    "update_payment",
    "create_payment_document",
    "get_payment_document",
    "list_payment_documents_by_status",
    "list_payments_for_invoice",
    "sum_payments_for_invoice",
    # Document line util
    "get_document_line_by_id",
    # Categories
    "get_category_by_id",
    "get_category_by_name",
    "list_categories",
    "list_active_categories",
    "create_category",
    "update_category",
    # Notes
    "get_note_by_id",
    "list_notes_by_invoice",
    "create_note",
    # Import logs
    "get_import_log_by_id",
    "list_import_logs",
    "list_import_logs_by_file_name",
    "get_import_log_by_file_hash",
    "find_document_by_file_hash",
    "create_import_log",
]