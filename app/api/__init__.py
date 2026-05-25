# app/api/__init__.py

from .api_documents import api_documents_bp
from .api_categories import api_categories_bp
from .api_delivery_notes import api_delivery_notes_bp

__all__ = [
    "api_documents_bp",
    "api_categories_bp",
    "api_delivery_notes_bp",
]
