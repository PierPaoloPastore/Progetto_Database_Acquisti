"""
Unit of Work Pattern.
Gestisce la transazione del database atomica e l'accesso ai repository.
"""
from functools import cached_property
from app.extensions import db

# Import Repositories
from app.repositories.category_repo import CategoryRepository
from app.repositories.supplier_repo import SupplierRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.credit_note_allocation_repo import CreditNoteAllocationRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.delivery_note_repo import DeliveryNoteRepository
from app.repositories.delivery_note_line_repo import DeliveryNoteLineRepository
from app.repositories.bank_account_repo import BankAccountRepository
from app.repositories.document_audit_log_repo import DocumentAuditLogRepository

class UnitOfWork:
    def __init__(self):
        self.session = db.session

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
            return False
        # Flask gestisce la chiusura della sessione, non chiudere qui

    @cached_property
    def categories(self) -> CategoryRepository:
        return CategoryRepository(self.session)

    @cached_property
    def suppliers(self) -> SupplierRepository:
        return SupplierRepository(self.session)

    @cached_property
    def payments(self) -> PaymentRepository:
        return PaymentRepository(self.session)

    @cached_property
    def credit_note_allocations(self) -> CreditNoteAllocationRepository:
        return CreditNoteAllocationRepository(self.session)
    
    @cached_property
    def delivery_notes(self) -> DeliveryNoteRepository:
        return DeliveryNoteRepository(self.session)

    @cached_property
    def delivery_note_lines(self) -> DeliveryNoteLineRepository:
        return DeliveryNoteLineRepository(self.session)

    @cached_property
    def documents(self) -> DocumentRepository:
        return DocumentRepository(self.session)

    @cached_property
    def bank_accounts(self) -> BankAccountRepository:
        return BankAccountRepository(self.session)

    @cached_property
    def document_audit_logs(self) -> DocumentAuditLogRepository:
        return DocumentAuditLogRepository(self.session)

    def commit(self):
        try:
            self.session.commit()
        except Exception:
            self.rollback()
            raise

    def rollback(self):
        self.session.rollback()
