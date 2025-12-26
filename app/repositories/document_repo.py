"""
Repository specifico per Document (Fatture).
Gestisce tutte le operazioni CRUD e di ricerca su tabella 'documents'.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from calendar import monthrange
import logging

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.models import ImportLog, Document, DocumentLine, LegalEntity, Payment, Supplier, VatSummary
from app.repositories.base import SqlAlchemyRepository
from app.parsers.fatturapa_parser import InvoiceDTO, InvoiceLineDTO, PaymentDTO, VatSummaryDTO

logger = logging.getLogger(__name__)

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
        document_number: Optional[str] = None,
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

        if document_number:
            query = query.filter(Document.document_number.ilike(f"%{document_number}%"))

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

    def list_imported(
        self,
        document_type: Optional[str] = None,
        order: str = "desc",
        legal_entity_id: Optional[int] = None,
        doc_status: str = "pending_physical_copy",
    ) -> List[Document]:
        """
        Restituisce documenti da revisionare (default: pending_physical_copy).
        """
        query = self.session.query(Document).filter(Document.doc_status == doc_status)
        if document_type:
            query = query.filter(Document.document_type == document_type)
        if legal_entity_id is not None:
            query = query.filter(Document.legal_entity_id == legal_entity_id)
        
        sort_order = Document.document_date.asc() if order == "asc" else Document.document_date.desc()
        return query.order_by(sort_order).all()

    def count_imported_by_legal_entity(self) -> List[tuple[int, int]]:
        """Ritorna (legal_entity_id, count) per documenti in revisione."""
        rows = (
            self.session.query(Document.legal_entity_id, func.count(Document.id))
            .filter(Document.doc_status == "pending_physical_copy")
            .group_by(Document.legal_entity_id)
            .all()
        )
        return rows

    def get_next_imported(
        self,
        document_type: Optional[str] = None,
        order: str = "desc",
        legal_entity_id: Optional[int] = None,
        doc_status: str = "pending_physical_copy",
    ) -> Optional[Document]:
        """Recupera il prossimo documento da revisionare."""
        query = self.session.query(Document).filter(Document.doc_status == doc_status)
        if document_type:
            query = query.filter(Document.document_type == document_type)
        if legal_entity_id is not None:
            query = query.filter(Document.legal_entity_id == legal_entity_id)
            
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

        tipo_documento = (getattr(invoice_dto, "tipo_documento", None) or "").upper()
        is_credit_note = tipo_documento == "TD04"
        document_type = "credit_note" if is_credit_note else "invoice"
        invoice_type = "deferred" if tipo_documento == "TD24" else "immediate"

        # Fallback robusti per i totali: alcuni XML arrivano senza riepiloghi completi
        # e il DB richiede total_gross_amount valorizzato.
        gross = invoice_dto.total_gross_amount
        taxable = invoice_dto.total_taxable_amount
        vat = invoice_dto.total_vat_amount

        # Calcola gross se mancante usando taxable + vat; se ancora None, usa 0
        if gross is None:
            gross = (taxable or Decimal("0")) + (vat or Decimal("0"))
        if gross is None:
            gross = Decimal("0")

        # Normalizza taxable/vat a 0 se None per coerenza
        taxable = taxable if taxable is not None else Decimal("0")
        vat = vat if vat is not None else Decimal("0")

        sign = -1 if is_credit_note else 1
        gross = _apply_credit_sign(gross, sign)
        taxable = _apply_credit_sign(taxable, sign)
        vat = _apply_credit_sign(vat, sign)

        supplier = self.session.get(Supplier, supplier_id)
        effective_due_date, used_fallback = _resolve_due_date(invoice_dto, supplier)

        allowed_statuses = {"pending_physical_copy", "verified", "archived"}
        status = invoice_dto.doc_status
        if status not in allowed_statuses:
            status = "pending_physical_copy"

        doc = Document(
            supplier_id=supplier_id,
            legal_entity_id=legal_entity_id,
            document_type=document_type,
            invoice_type=invoice_type,
            document_number=invoice_dto.invoice_number,
            document_date=invoice_dto.invoice_date,
            registration_date=invoice_dto.registration_date,
            total_taxable_amount=taxable,
            total_vat_amount=vat,
            total_gross_amount=gross,
            doc_status=status,
            due_date=effective_due_date,
            file_name=invoice_dto.file_name,
            import_source=import_source,
            note=getattr(invoice_dto, "note", None),
        )
        
        self.add(doc)
        self.session.flush() # Otteniamo ID

        if invoice_dto.lines:
            for line_dto in invoice_dto.lines:
                self._create_line(doc.id, line_dto, sign=sign)
        
        if invoice_dto.vat_summaries:
            for vat_dto in invoice_dto.vat_summaries:
                self._create_vat_summary(doc.id, vat_dto, sign=sign)

        if invoice_dto.payments and not is_credit_note:
            for pay_dto in invoice_dto.payments:
                self._create_payment(doc, pay_dto)
        elif invoice_dto.payments and is_credit_note:
            logger.info(
                "Pagamenti ignorati per nota di credito",
                extra={
                    "document_id": doc.id,
                    "file_name": invoice_dto.file_name,
                    "tipo_documento": tipo_documento or None,
                },
            )

        if used_fallback:
            logger.info(
                "Scadenza calcolata da regola fornitore",
                extra={
                    "supplier_id": supplier_id,
                    "document_id": doc.id,
                    "due_date": effective_due_date.isoformat() if effective_due_date else None,
                    "invoice_date": invoice_dto.invoice_date.isoformat() if invoice_dto.invoice_date else None,
                    "typical_due_rule": getattr(supplier, "typical_due_rule", None),
                    "typical_due_days": getattr(supplier, "typical_due_days", None),
                },
            )

        return doc, True

    def _create_line(self, doc_id: int, dto: InvoiceLineDTO, sign: int = 1):
        line = DocumentLine(
            document_id=doc_id,
            line_number=dto.line_number,
            description=dto.description or "N/D",
            quantity=dto.quantity,
            unit_price=_apply_credit_sign(dto.unit_price, sign),
            total_line_amount=_apply_credit_sign(dto.total_line_amount, sign),
            taxable_amount=_apply_credit_sign(dto.taxable_amount, sign),
            vat_rate=dto.vat_rate,
            vat_amount=_apply_credit_sign(dto.vat_amount, sign),
        )
        self.session.add(line)

    def _create_vat_summary(self, doc_id: int, dto: VatSummaryDTO, sign: int = 1):
        summary = VatSummary(
            document_id=doc_id,
            vat_rate=dto.vat_rate,
            taxable_amount=_apply_credit_sign(dto.taxable_amount, sign),
            vat_amount=_apply_credit_sign(dto.vat_amount, sign),
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


def _end_of_month(base: date) -> date:
    last_day = monthrange(base.year, base.month)[1]
    return date(base.year, base.month, last_day)


def _next_month_day_1(base: date) -> date:
    year = base.year + (1 if base.month == 12 else 0)
    month = 1 if base.month == 12 else base.month + 1
    return date(year, month, 1)


def _apply_rule(base: date, rule: Optional[str], days: Optional[int]) -> date:
    """
    Applica regola o giorni custom; default = end_of_month.
    """
    if rule == "immediate":
        return base
    if rule == "net_30":
        return base + timedelta(days=30)
    if rule == "net_60":
        return base + timedelta(days=60)
    if rule == "next_month_day_1":
        return _next_month_day_1(base)
    if rule == "end_of_month":
        return _end_of_month(base)
    if days is not None:
        return base + timedelta(days=days)
    # Default assoluto: ultimo giorno del mese della data base
    return _end_of_month(base)


def _resolve_due_date(invoice_dto: InvoiceDTO, supplier: Optional[Supplier]) -> tuple[Optional[date], bool]:
    """
    Ritorna (due_date, used_fallback) applicando la regola del fornitore
    se la scadenza manca o coincide con la data documento.
    """
    original_due = invoice_dto.due_date
    invoice_date = invoice_dto.invoice_date
    base_date = invoice_date or invoice_dto.registration_date or date.today()
    rule = getattr(supplier, "typical_due_rule", None)
    days = getattr(supplier, "typical_due_days", None)

    if original_due and invoice_date and original_due != invoice_date:
        return original_due, False

    if original_due is None or (invoice_date and original_due == invoice_date):
        computed_due = _apply_rule(base_date, rule, days)
        return computed_due, True

    return original_due, False


def _apply_credit_sign(value: Optional[Decimal], sign: int) -> Optional[Decimal]:
    if value is None:
        return None
    if sign < 0 and value > 0:
        return -value
    return value
