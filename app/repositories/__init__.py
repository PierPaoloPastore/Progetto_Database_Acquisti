"""
Package repositories.
Espone i Repository per l'accesso ai dati.
"""

from .category_repo import CategoryRepository
from .supplier_repo import SupplierRepository
from .payment_repo import PaymentRepository
from .document_repo import DocumentRepository # <--- Nuova Classe

# Import Log e altre utilità rimaste a funzioni (se non le hai rifattorizzate)
# Assumiamo che import_log_repo, legal_entity_repo ecc. siano ancora moduli con funzioni,
# oppure se li hai rifattorizzati, usa le classi. 
# Per sicurezza, mantengo gli import che non abbiamo toccato in questa sessione
# ma rimuovo quelli di document/invoice che causano errore.

from .import_log_repo import create_import_log
from .legal_entity_repo import list_legal_entities
from .document_line_repo import get_document_line_by_id, list_lines_by_document

__all__ = [
    "CategoryRepository",
    "SupplierRepository",
    "PaymentRepository",
    "DocumentRepository",
    "create_import_log",
    "list_legal_entities",
    "get_document_line_by_id",
    "list_lines_by_document",
]