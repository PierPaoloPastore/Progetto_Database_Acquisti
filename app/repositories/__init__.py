"""
Pacchetto per i repository che incapsulano l'accesso ai dati.

La logica di business rimane nei servizi (app.services.*).
"""

from .supplier_repo import (
    get_supplier_by_id,
    get_supplier_by_vat_number,
    get_supplier_by_tax_code,
    list_suppliers,
    create_supplier,
    update_supplier,
    get_or_create_supplier_from_dto,
)
from .legal_entity_repo import list_legal_entities, get_legal_entity_by_id
# Repository preferito per le fatture: re-export per compatibilita.
from .invoice_repository import (
    get_invoice_by_id,
    get_invoice_by_file_name,
    get_invoice_by_file_hash,
    find_existing_invoice,
    list_invoices,
    search_invoices_by_filters,
    list_accounting_years,
    filter_invoices_by_date_range,
    filter_invoices_by_supplier,
    filter_invoices_by_payment_status,
    create_invoice,
    update_invoice,
    create_invoice_with_details,
    get_supplier_account_balance,
    list_supplier_legal_entities,
)
from .invoice_line_repo import (
    get_invoice_line_by_id,
    list_lines_by_invoice,
    list_lines_by_category,
    create_invoice_line,
    update_invoice_line,
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
)
from .category_repo import (
    get_category_by_id,
    get_category_by_name,
    list_categories,
    list_active_categories,
    create_category,
    update_category,
)
from .notes_repo import (
    get_note_by_id,
    list_notes_by_invoice,
    create_note,
)
from .import_log_repo import (
    get_import_log_by_id,
    list_import_logs,
    list_import_logs_by_file_name,
    create_import_log,
)

__all__ = [
    # Suppliers
    "get_supplier_by_id",
    "get_supplier_by_vat_number",
    "get_supplier_by_tax_code",
    "list_suppliers",
    "create_supplier",
    "update_supplier",
    "get_or_create_supplier_from_dto",
    # Legal entities
    "list_legal_entities",
    "get_legal_entity_by_id",
    # Invoices
    "get_invoice_by_id",
    "get_invoice_by_file_name",
    "get_invoice_by_file_hash",
    "find_existing_invoice",
    "list_invoices",
    "search_invoices_by_filters",
    "list_accounting_years",
    "filter_invoices_by_date_range",
    "filter_invoices_by_supplier",
    "filter_invoices_by_payment_status",
    "create_invoice",
    "update_invoice",
    "create_invoice_with_details",
    "get_supplier_account_balance",
    "list_supplier_legal_entities",
    # Invoice lines
    "list_lines_by_invoice",
    "list_lines_by_category",
    "create_invoice_line",
    "update_invoice_line",
    # VAT summaries
    "list_vat_summaries_by_invoice",
    "create_vat_summary",
    # Payments
    "get_payment_by_id",
    "list_payments_by_invoice",
    "list_overdue_payments",
    "create_payment",
    "update_payment",
    # Invoice line util
    "get_invoice_line_by_id",
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
    "create_import_log",
]
