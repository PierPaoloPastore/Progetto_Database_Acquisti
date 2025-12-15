"""
Repository specifico per Document (Fatture).
Gestisce tutte le operazioni CRUD e di ricerca su tabella 'documents'.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.models import ImportLog, Document, DocumentLine, LegalEntity, Payment, VatSummary
from app.repositories.base import SqlAlchemyRepository
from app.parsers.fatturapa_parser import InvoiceDTO, InvoiceLineDTO, PaymentDTO, VatSummaryDTO

class DocumentRepository(SqlAlchemyRepository[Document]):
    def __init__(self, session):
        super().__init__(session, Document)

    def get_by_id(self, doc_id: int) -> Optional[Document]:
        """Restituisce un documento dato l'ID, includendo le relazioni principali."""
        if doc_id is None:
            return None
        return (
            self.session.query(Document)
            .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
            .filter(Document.id == doc_id)
            .one_or_none()
        )

    def get_by_file_name(self, file_name: str) -> Optional[Document]:
        if not file_name:
            return None
        return self.session.query(Document).filter_by(file_name=file_name).first()

    def get_by_file_hash(self, file_hash: str) -> Optional[Document]:
        if not file_hash:
            return None
        import_log = (
            self.session.query(ImportLog)
            .filter(ImportLog.file_hash == file_hash)
            .filter(ImportLog.document_id.isnot(None))
            .order_by(ImportLog.created_at.desc())
            .first()
        )
        if import_log and import_log.document_id:
            return self.get_by_id(import_log.document_id)
        return None

    def find_existing(self, file_name: Optional[str] = None, file_hash: Optional[str] = None) -> Optional[Document]:
        """Cerca se esiste già un documento simile."""
        if file_name:
            existing = self.get_by_file_name(file_name)
            if existing:
                return existing
        if file_hash:
            return self.get_by_file_hash(file_hash)
        return None

    def search(
        self,
        *,
        document_type: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        supplier_id: Optional[int] = None,
        doc_status: Optional[str] = None,
        payment_status: Optional[str] = None,
        physical_copy_status: Optional[str] = None,
        legal_entity_id: Optional[int] = None,
        accounting_year: Optional[int] = None,
        min_total: Optional[Decimal] = None,
        max_total: Optional[Decimal] = None,
        limit: Optional[int] = 200,
    ) -> List[Document]:
        """Ricerca documenti avanzata."""
        query = self.session.query(Document)

        if document_type:
            query = query.filter(Document.document_type == document_type)

        if payment_status is not None:
            query = query.join(Payment, Payment.document_id == Document.id).filter(
                Payment.status == payment_status
            )

        if legal_entity_id is not None:
            query = query.filter(Document.legal_entity_id == legal_entity_id)
        if accounting_year is not None:
            query = query.filter(func.year(Document.document_date) == accounting_year)
        if supplier_id is not None:
            query = query.filter(Document.supplier_id == supplier_id)
        if doc_status is not None:
            query = query.filter(Document.doc_status == doc_status)
        if physical_copy_status is not None:
            query = query.filter(Document.physical_copy_status == physical_copy_status)

        if date_from is not None:
            query = query.filter(Document.document_date >= date_from)
        if date_to is not None:
            query = query.filter(Document.document_date <= date_to)

        if min_total is not None:
            query = query.filter(Document.total_gross_amount >= min_total)
        if max_total is not None:
            query = query.filter(Document.total_gross_amount <= max_total)

        query = query.order_by(Document.document_date.desc(), Document.id.desc())

        if payment_status is not None:
            query = query.distinct()

        if limit is not None:
            query = query.limit(limit)

        return query.all()

    def list_imported(self, document_type: Optional[str] = None, order: str = "desc") -> List[Document]:
        """Restituisce documenti in stato 'imported' (da revisionare)."""
        query = self.session.query(Document).filter(Document.doc_status == "imported")
        if document_type:
            query = query.filter(Document.document_type == document_type)
        
        sort_order = Document.document_date.asc() if order == "asc" else Document.document_date.desc()
        return query.order_by(sort_order).all()

    def get_next_imported(self, document_type: Optional[str] = None, order: str = "desc") -> Optional[Document]:
        """Recupera il prossimo documento da revisionare."""
        query = self.session.query(Document).filter(Document.doc_status == "imported")
        if document_type:
            query = query.filter(Document.document_type == document_type)
            
        sort_order = Document.document_date.asc() if order == "asc" else Document.document_date.desc()
        return query.order_by(sort_order).first()

    def list_accounting_years(self) -> List[int]:
        """Restituisce tutti gli anni fiscali presenti."""
        rows = (
            self.session.query(func.year(Document.document_date))
            .filter(Document.document_date.isnot(None))
            .distinct()
            .order_by(func.year(Document.document_date).desc())
            .all()
        )
        return [row[0] for row in rows]

    def get_supplier_account_balance(self, supplier_id: int, legal_entity_id: Optional[int] = None) -> Dict:
        """Calcola estratto conto fornitore."""
        query = (
            self.session.query(
                func.coalesce(func.sum(Document.total_gross_amount), 0),
                func.coalesce(func.sum(Payment.paid_amount), 0),
                func.count(func.distinct(Document.id)),
            )
            .select_from(Document)
            .outerjoin(Payment, Payment.document_id == Document.id)
            .filter(Document.supplier_id == supplier_id)
            .filter(Document.doc_status != 'cancelled')
        )

        if legal_entity_id is not None:
            query = query.filter(Document.legal_entity_id == legal_entity_id)

        expected_total, paid_total, doc_count = query.one()
        residual = expected_total - paid_total

        return {
            "expected_total": expected_total,
            "paid_total": paid_total,
            "residual": residual,
            "document_count": doc_count,
        }

    # --- Metodi di Creazione ---

    def create_from_fatturapa(
        self,
        *,
        invoice_dto: InvoiceDTO,
        supplier_id: int,
        legal_entity_id: int,
        import_source: Optional[str] = None,
    ) -> Tuple[Document, bool]:
        """
        Crea un Document (type='invoice') partendo da un DTO FatturaPA.
        """
        existing = self.find_existing(
            file_name=invoice_dto.file_name,
            file_hash=getattr(invoice_dto, 'file_hash', None),
        )
        if existing:
            return existing, False

        doc = Document(
            supplier_id=supplier_id,
            legal_entity_id=legal_entity_id,
            document_type="invoice",
            document_number=invoice_dto.invoice_number,
            document_date=invoice_dto.invoice_date,
            registration_date=invoice_dto.registration_date,
            total_taxable_amount=invoice_dto.total_taxable_amount,
            total_vat_amount=invoice_dto.total_vat_amount,
            total_gross_amount=invoice_dto.total_gross_amount,
            doc_status=invoice_dto.doc_status,
            due_date=invoice_dto.due_date,
            file_name=invoice_dto.file_name,
            import_source=import_source,
        )
        
        self.add(doc)
        self.session.flush() # Otteniamo ID

        if invoice_dto.lines:
            for line_dto in invoice_dto.lines:
                self._create_line(doc.id, line_dto)
        
        if invoice_dto.vat_summaries:
            for vat_dto in invoice_dto.vat_summaries:
                self._create_vat_summary(doc.id, vat_dto)

        if invoice_dto.payments:
            for pay_dto in invoice_dto.payments:
                self._create_payment(doc, pay_dto)

        return doc, True

    def _create_line(self, doc_id: int, dto: InvoiceLineDTO):
        line = DocumentLine(
            document_id=doc_id,
            line_number=dto.line_number,
            description=dto.description or "N/D",
            quantity=dto.quantity,
            unit_price=dto.unit_price,
            total_line_amount=dto.total_line_amount,
            taxable_amount=dto.taxable_amount,
            vat_rate=dto.vat_rate,
            vat_amount=dto.vat_amount
        )
        self.session.add(line)

    def _create_vat_summary(self, doc_id: int, dto: VatSummaryDTO):
        summary = VatSummary(
            document_id=doc_id,
            vat_rate=dto.vat_rate,
            taxable_amount=dto.taxable_amount,
            vat_amount=dto.vat_amount,
            vat_nature=dto.vat_nature,
        )
        self.session.add(summary)

    def _create_payment(self, doc: Document, dto: PaymentDTO):
        payment = Payment(
            document_id=doc.id,
            due_date=dto.due_date,
            expected_amount=dto.expected_amount,
            payment_terms=dto.payment_terms,
            payment_method=dto.payment_method,
            status="unpaid",
        )
        self.session.add(payment)
        if doc.due_date is None and dto.due_date:
            doc.due_date = dto.due_date