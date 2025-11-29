"""
Pacchetto per i servizi (logica di business) dell'applicazione.

I servizi orchestrano:
- repository (accesso al DB)
- parser (es. FatturaPA XML)
- validazioni e transazioni
- logging strutturato
"""

from .import_service import run_import
from .invoice_service import (
    search_invoices,
    get_invoice_detail,
    update_invoice_status,
    mark_physical_copy_received,
)
from .supplier_service import (
    list_suppliers_with_stats,
    get_supplier_detail,
)
from .category_service import (
    list_categories_for_ui,
    create_or_update_category,
    assign_category_to_line,
    bulk_assign_category_to_invoice_lines,
)
from .payment_service import (
    list_overdue_payments_for_ui,
    generate_payment_schedule,
    create_payment,
    update_payment,
)

__all__ = [
    # Import
    "run_import",
    # Invoices
    "search_invoices",
    "get_invoice_detail",
    "update_invoice_status",
    "mark_physical_copy_received",
    # Suppliers
    "list_suppliers_with_stats",
    "get_supplier_detail",
    # Categories
    "list_categories_for_ui",
    "create_or_update_category",
    "assign_category_to_line",
    "bulk_assign_category_to_invoice_lines",
    # Payments
    "list_overdue_payments_for_ui",
    "generate_payment_schedule",
    "create_payment",
    "update_payment",
]
