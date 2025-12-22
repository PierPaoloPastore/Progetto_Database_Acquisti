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
    update_supplier,
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
    list_paid_payments,
    get_payment_event_detail,
    add_payment,
    delete_payment,
)
from .settings_service import get_setting, set_setting
from .delivery_note_service import (
    list_delivery_notes,
    get_delivery_note,
    get_delivery_note_with_lines,
    list_delivery_notes_by_document,
    create_delivery_note,
    get_delivery_note_file_path,
    upsert_delivery_note_lines,
    find_delivery_note_candidates,
    link_delivery_note_to_document,
)

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
    "update_supplier",
    # Categories
    "list_categories_for_ui",
    "create_or_update_category",
    "assign_category_to_line",
    "bulk_assign_category_to_invoice_lines",
    # Payments
    "list_overdue_payments_for_ui",
    "list_payments_by_document",
    "list_paid_payments",
    "get_payment_event_detail",
    "add_payment",
    "delete_payment",
    # Settings
    "get_setting",
    "set_setting",
    # Delivery Notes
    "list_delivery_notes",
    "get_delivery_note",
    "get_delivery_note_with_lines",
    "list_delivery_notes_by_document",
    "create_delivery_note",
    "get_delivery_note_file_path",
    "upsert_delivery_note_lines",
    "find_delivery_note_candidates",
    "link_delivery_note_to_document",
]
