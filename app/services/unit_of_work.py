"""
Unit of Work Pattern.
Gestisce la transazione del database atomica e l'accesso ai repository.
"""
from typing import Optional
from app.extensions import db

# Import Repositories
from app.repositories.category_repo import CategoryRepository
from app.repositories.supplier_repo import SupplierRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.delivery_note_repo import DeliveryNoteRepository
from app.repositories.delivery_note_line_repo import DeliveryNoteLineRepository

class UnitOfWork:
    def __init__(self):
        self.session = db.session
        self._categories: Optional[CategoryRepository] = None
        self._suppliers: Optional[SupplierRepository] = None
        self._payments: Optional[PaymentRepository] = None
        self._documents: Optional[DocumentRepository] = None
        self._delivery_notes: Optional[DeliveryNoteRepository] = None
        self._delivery_note_lines: Optional[DeliveryNoteLineRepository] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
            return False
        # Flask gestisce la chiusura della sessione, non chiudere qui

    @property
    def categories(self) -> CategoryRepository:
        if self._categories is None:
            self._categories = CategoryRepository(self.session)
        return self._categories

    @property
    def suppliers(self) -> SupplierRepository:
        if self._suppliers is None:
            self._suppliers = SupplierRepository(self.session)
        return self._suppliers

    @property
    def payments(self) -> PaymentRepository:
        if self._payments is None:
            self._payments = PaymentRepository(self.session)
        return self._payments
    
    @property
    def delivery_notes(self) -> DeliveryNoteRepository:
        if self._delivery_notes is None:
            self._delivery_notes = DeliveryNoteRepository(self.session)
        return self._delivery_notes

    @property
    def delivery_note_lines(self) -> DeliveryNoteLineRepository:
        if self._delivery_note_lines is None:
            self._delivery_note_lines = DeliveryNoteLineRepository(self.session)
        return self._delivery_note_lines

    @property
    def documents(self) -> DocumentRepository:
        if self._documents is None:
            self._documents = DocumentRepository(self.session)
        return self._documents

    def commit(self):
        try:
            self.session.commit()
        except Exception:
            self.rollback()
            raise

    def rollback(self):
        self.session.rollback()
