"""
Pacchetto per i servizi (logica di business) dell'applicazione.

I servizi orchestrano:
- repository (accesso al DB)
- parser (es. FatturaPA XML)
- validazioni e transazioni
- logging strutturato
"""

from .import_service import run_import
from .document_service import (
    search_documents,
    get_document_detail,
    update_document_status,
    confirm_document,
    reject_document,
    list_documents_to_review,
    get_next_document_to_review,
    list_documents_without_physical_copy,
    mark_physical_copy_received,
    request_physical_copy,
    DocumentService,
)
from .supplier_service import (
    list_suppliers_with_stats,
    get_supplier_detail,
    list_active_suppliers, # Aggiunto
)
from .category_service import (
    list_categories_for_ui,
    create_or_update_category,
    assign_category_to_line,
    bulk_assign_category_to_invoice_lines,
)
# AGGIORNATO: Importiamo solo le funzioni esistenti nel nuovo payment_service
from .payment_service import (
    list_overdue_payments_for_ui,
    list_payments_by_document,
    add_payment,
    delete_payment,
)
from .settings_service import get_setting, set_setting

__all__ = [
    # Import
    "run_import",
    # Documents (ex Invoices)
    "search_documents",
    "get_document_detail",
    "update_document_status",
    "confirm_document",
    "reject_document",
    "list_documents_to_review",
    "get_next_document_to_review",
    "list_documents_without_physical_copy",
    "mark_physical_copy_received",
    "request_physical_copy",
    "DocumentService",
    # Suppliers
    "list_suppliers_with_stats",
    "get_supplier_detail",
    "list_active_suppliers",
    # Categories
    "list_categories_for_ui",
    "create_or_update_category",
    "assign_category_to_line",
    "bulk_assign_category_to_invoice_lines",
    # Payments
    "list_overdue_payments_for_ui",
    "list_payments_by_document",
    "add_payment",
    "delete_payment",
    # Settings
    "get_setting",
    "set_setting",
]