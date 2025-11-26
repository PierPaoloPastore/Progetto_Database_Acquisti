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
from .invoice_repository import (
    get_invoice_by_id,
    get_invoice_by_file_name,
    get_invoice_by_file_hash,
    find_existing_invoice,
    list_invoices,
    filter_invoices_by_date_range,
    filter_invoices_by_supplier,
    filter_invoices_by_payment_status,
    create_invoice,
    update_invoice,
    list_lines_by_invoice,
    list_lines_by_category,
    create_invoice_line,
    update_invoice_line,
    list_vat_summaries_by_invoice,
    create_vat_summary,
    list_payments_by_invoice,
    list_overdue_payments,
    get_payment_by_id,
    create_payment,
    update_payment,
    create_invoice_with_details,
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
    # Invoices
    "get_invoice_by_id",
    "get_invoice_by_file_name",
    "get_invoice_by_file_hash",
    "find_existing_invoice",
    "list_invoices",
    "filter_invoices_by_date_range",
    "filter_invoices_by_supplier",
    "filter_invoices_by_payment_status",
    "create_invoice",
    "update_invoice",
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
    # Composto
    "create_invoice_with_details",
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
