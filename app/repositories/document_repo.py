"""
Repository per la gestione dei Documenti (ex Invoice).
Gestisce tutte le operazioni CRUD su tabella 'documents'.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import ImportLog, Document, DocumentLine, LegalEntity, Payment, VatSummary
# Nota: Importiamo i DTO, ma li usiamo per creare un generico Document
from app.parsers.fatturapa_parser import InvoiceDTO, InvoiceLineDTO, PaymentDTO, VatSummaryDTO

def get_document_by_id(doc_id: int) -> Optional[Document]:
    """Restituisce un documento dato l'ID, includendo fornitore e legal entity."""
    if doc_id is None:
        return None
    return (
        db.session.query(Document)
        .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
        .filter(Document.id == doc_id)
        .one_or_none()
    )

def get_document_by_file_name(file_name: str) -> Optional[Document]:
    if not file_name:
        return None
    return Document.query.filter_by(file_name=file_name).first()

def get_document_by_file_hash(file_hash: str) -> Optional[Document]:
    if not file_hash:
        return None
    import_log = (
        ImportLog.query
        .filter(ImportLog.file_hash == file_hash)
        .filter(ImportLog.document_id.isnot(None))
        .order_by(ImportLog.created_at.desc())
        .first()
    )
    if import_log and import_log.document_id:
        return get_document_by_id(import_log.document_id)
    return None

def find_existing_document(file_name: Optional[str] = None, file_hash: Optional[str] = None) -> Optional[Document]:
    if file_name:
        existing = Document.query.filter_by(file_name=file_name).first()
        if existing:
            return existing
    if file_hash:
        return get_document_by_file_hash(file_hash)
    return None

def search_documents(
    *,
    document_type: Optional[str] = None,  # NUOVO FILTRO
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
    """Ricerca documenti generica."""
    query = db.session.query(Document)

    # Filtro base sul tipo documento (es. mostrare solo fatture o solo F24)
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

def list_imported_documents(document_type: Optional[str] = None, order: str = "desc") -> List[Document]:
    """Restituisce documenti in stato 'imported'."""
    query = Document.query.filter(Document.doc_status == "imported")
    if document_type:
        query = query.filter(Document.document_type == document_type)
    
    sort_order = Document.document_date.asc() if order == "asc" else Document.document_date.desc()
    return query.order_by(sort_order).all()

def get_next_imported_document(document_type: Optional[str] = None, order: str = "desc") -> Optional[Document]:
    query = Document.query.filter(Document.doc_status == "imported")
    if document_type:
        query = query.filter(Document.document_type == document_type)
        
    sort_order = Document.document_date.asc() if order == "asc" else Document.document_date.desc()
    return query.order_by(sort_order).first()

# --- Metodi di Creazione ---

def create_document(**kwargs) -> Document:
    """Crea un documento generico."""
    if kwargs.get("legal_entity_id") is None:
        raise ValueError("legal_entity_id è obbligatorio")
    
    # Assicuriamo che ci sia un document_type
    if "document_type" not in kwargs:
        kwargs["document_type"] = "other"

    doc = Document(**kwargs)
    db.session.add(doc)
    return doc

def update_document(document: Document, **kwargs) -> Document:
    for key, value in kwargs.items():
        if hasattr(document, key):
            setattr(document, key, value)
    return document

# --- Metodi Specifici per FatturaPA (Import XML) ---
# Manteniamo la logica specifica qui, ma restituiamo un Document

def create_document_from_fatturapa(
    *,
    invoice_dto: InvoiceDTO,
    supplier_id: int,
    legal_entity_id: int,
    import_source: Optional[str] = None,
) -> Tuple[Document, bool]:
    """
    Crea un Document (type='invoice') partendo da un DTO FatturaPA.
    """
    existing = find_existing_document(
        file_name=invoice_dto.file_name,
        file_hash=getattr(invoice_dto, 'file_hash', None),
    )
    if existing:
        return existing, False

    doc_kwargs = {
        "supplier_id": supplier_id,
        "legal_entity_id": legal_entity_id,
        "document_type": "invoice",  # FORZIAMO IL TIPO
        "document_number": invoice_dto.invoice_number,
        "document_date": invoice_dto.invoice_date,
        "registration_date": invoice_dto.registration_date,
        "total_taxable_amount": invoice_dto.total_taxable_amount,
        "total_vat_amount": invoice_dto.total_vat_amount,
        "total_gross_amount": invoice_dto.total_gross_amount,
        "doc_status": invoice_dto.doc_status,
        "due_date": invoice_dto.due_date,
        "file_name": invoice_dto.file_name,
        "import_source": import_source,
    }

    document = create_document(**doc_kwargs)
    db.session.flush()

    # Le righe e i dettagli sono gli stessi, collegati via document_id
    if invoice_dto.lines:
        for line_dto in invoice_dto.lines:
            _create_line(document.id, line_dto)
    
    if invoice_dto.vat_summaries:
        for vat_dto in invoice_dto.vat_summaries:
            _create_vat_summary(document.id, vat_dto)

    if invoice_dto.payments:
        for pay_dto in invoice_dto.payments:
            _create_payment(document, pay_dto)

    return document, True

def _create_line(doc_id: int, dto: InvoiceLineDTO):
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
    db.session.add(line)

def _create_vat_summary(doc_id: int, dto: VatSummaryDTO):
    summary = VatSummary(
        document_id=doc_id,
        vat_rate=dto.vat_rate,
        taxable_amount=dto.taxable_amount,
        vat_amount=dto.vat_amount,
        vat_nature=dto.vat_nature,
    )
    db.session.add(summary)

def _create_payment(doc: Document, dto: PaymentDTO):
    payment = Payment(
        document_id=doc.id,
        due_date=dto.due_date,
        expected_amount=dto.expected_amount,
        payment_terms=dto.payment_terms,
        payment_method=dto.payment_method,
        status="unpaid",
    )
    db.session.add(payment)
    # Aggiorna la scadenza principale del documento se mancante
    if doc.due_date is None and dto.due_date:
        doc.due_date = dto.due_date

        # --- Funzioni di Utilità / Statistiche (Da aggiungere in fondo a document_repo.py) ---

def list_accounting_years() -> List[int]:
    """
    Restituisce tutti gli anni presenti nei documenti (per i filtri a tendina).
    Basato su YEAR(document_date).
    """
    rows = (
        db.session.query(func.year(Document.document_date))
        .filter(Document.document_date.isnot(None))
        .distinct()
        .order_by(func.year(Document.document_date).desc())
        .all()
    )
    return [row[0] for row in rows]

def get_supplier_account_balance(
    supplier_id: int, legal_entity_id: Optional[int] = None
) -> Dict[str, Decimal | int]:
    """
    Calcola l'estratto conto di un fornitore (totale atteso vs pagato).
    """
    query = (
        db.session.query(
            func.coalesce(func.sum(Document.total_gross_amount), 0),
            func.coalesce(func.sum(Payment.paid_amount), 0),
            func.count(func.distinct(Document.id)),
        )
        .select_from(Document)
        .outerjoin(Payment, Payment.document_id == Document.id)
        .filter(Document.supplier_id == supplier_id)
        # Escludiamo documenti annullati o non rilevanti se necessario
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

def list_supplier_legal_entities(supplier_id: int) -> List[Dict[str, int | str]]:
    """
    Elenca le società (LegalEntity) che hanno ricevuto fatture da questo fornitore.
    """
    rows = (
        db.session.query(
            LegalEntity.id.label("id"),
            LegalEntity.name.label("name"),
            func.count(Document.id).label("doc_count"),
        )
        .join(Document, Document.legal_entity_id == LegalEntity.id)
        .filter(Document.supplier_id == supplier_id)
        .group_by(LegalEntity.id, LegalEntity.name)
        .order_by(LegalEntity.name.asc())
        .all()
    )

    return [
        {
            "id": row.id,
            "name": row.name,
            "doc_count": row.doc_count,
        }
        for row in rows
    ]