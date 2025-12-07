"""
Backward compatibility: Invoice è ora un alias di Document.
Usa Document direttamente nel nuovo codice.
"""
from app.models.document import Document as Invoice

__all__ = ['Invoice']
