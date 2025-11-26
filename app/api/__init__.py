"""
Pacchetto per le API leggere (JSON) usate da JS sul frontend.

Contiene:
- api_invoices_bp   -> API legate alle fatture (stato, categorie righe, ecc.)
- api_categories_bp -> API legate alle categorie (assegnazione bulk, elenco)
"""

from .api_invoices import api_invoices_bp
from .api_categories import api_categories_bp

__all__ = [
    "api_invoices_bp",
    "api_categories_bp",
]
