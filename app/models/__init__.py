"""
Pacchetto per i modelli SQLAlchemy.

Qui vengono esportate le classi modello principali:
- LegalEntity
- Supplier
- Invoice
- InvoiceLine
- VatSummary
- Payment
- Category
- Note
- ImportLog
- User
"""

from .legal_entity import LegalEntity
from .supplier import Supplier
from .invoice import Invoice
from .invoice_line import InvoiceLine
from .vat_summary import VatSummary
from .payment import Payment
from .category import Category
from .note import Note
from .import_log import ImportLog
from .user import User

__all__ = [
    "LegalEntity",
    "Supplier",
    "Invoice",
    "InvoiceLine",
    "VatSummary",
    "Payment",
    "Category",
    "Note",
    "ImportLog",
    "User",
]
