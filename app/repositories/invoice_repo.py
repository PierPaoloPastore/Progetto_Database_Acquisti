from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, or_  # questo rimane in alto nel file
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Invoice, InvoiceLine, LegalEntity, Payment, VatSummary
from app.parsers.fatturapa_parser import InvoiceDTO, InvoiceLineDTO, PaymentDTO, VatSummaryDTO


# NOTA: accounting_year non è più una colonna fisica nel DB.
# L'anno contabile si deduce da YEAR(document_date) dove necessario.


def get_invoice_by_id(invoice_id: int) -> Optional[Invoice]:
    """Restituisce una fattura dato l'ID, includendo il fornitore collegato."""
    if invoice_id is None:
        return None
    return (
        db.session.query(Invoice)
        .options(joinedload(Invoice.supplier), joinedload(Invoice.legal_entity))
        .filter(Invoice.id == invoice_id)
        .one_or_none()
    )


def get_invoice_by_file_name(file_name: str) -> Optional[Invoice]:
    """Restituisce la fattura associata a un determinato nome file XML, se esiste."""
    if not file_name:
        return None
    return Invoice.query.filter_by(file_name=file_name).first()


def get_invoice_by_file_hash(file_hash: str) -> Optional[Invoice]:
    """Restituisce la fattura associata a un determinato hash di file, se esiste."""
    if not file_hash:
        return None
    return Invoice.query.filter_by(file_hash=file_hash).first()


def find_existing_invoice(
    file_name: Optional[str] = None, file_hash: Optional[str] = None
) -> Optional[Invoice]:
    """Cerca una fattura già importata confrontando file_name e/o file_hash."""
    filters = []
    if file_hash:
        filters.append(Invoice.file_hash == file_hash)
    if file_name:
        filters.append(Invoice.file_name == file_name)

    if not filters:
        return None

    return Invoice.query.filter(or_(*filters)).first()


def list_invoices(limit: Optional[int] = 200) -> List[Invoice]:
    """
    Restituisce una lista di fatture ordinate per data e ID decrescente.

    :param limit: massimo numero di record da restituire.
    """
    query = Invoice.query.order_by(
        Invoice.document_date.desc(),
        Invoice.id.desc(),
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def _apply_invoice_ordering(query, order: str):
    sort_order = order if order in {"asc", "desc"} else "desc"
    if sort_order == "asc":
        return query.order_by(Invoice.document_date.asc(), Invoice.id.asc())
    return query.order_by(Invoice.document_date.desc(), Invoice.id.desc())


def list_imported_invoices(order: str = "desc") -> List[Invoice]:
    """Restituisce le fatture con stato documento "imported" ordinate per data."""
    query = Invoice.query.filter(Invoice.doc_status == "imported")
    query = _apply_invoice_ordering(query, order)
    return query.all()


def list_invoices_without_physical_copy(order: str = "desc") -> List[Invoice]:
    """Restituisce le fatture senza copia fisica o con copia richiesta."""
    query = Invoice.query.filter(
        Invoice.physical_copy_status.in_(["missing", "requested"])
    )
    query = _apply_invoice_ordering(query, order)
    return query.all()


def get_next_imported_invoice(order: str = "desc") -> Optional[Invoice]:
    """Restituisce la prossima fattura da rivedere in base all'ordinamento scelto."""
    query = Invoice.query.filter(Invoice.doc_status == "imported")
    query = _apply_invoice_ordering(query, order)
    return query.first()


def search_invoices_by_filters(
    *,
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
) -> List[Invoice]:
    """Ricerca fatture applicando tutti i filtri supportati dall'UI elenco."""
    query = Invoice.query

    if legal_entity_id is not None:
        query = query.filter(Invoice.legal_entity_id == legal_entity_id)
    if accounting_year is not None:
        query = query.filter(func.year(Invoice.document_date) == accounting_year)
    if supplier_id is not None:
        query = query.filter(Invoice.supplier_id == supplier_id)
    if doc_status is not None:
        query = query.filter(Invoice.doc_status == doc_status)
    if payment_status is not None:
        query = query.filter(Invoice.payment_status == payment_status)
    if physical_copy_status is not None:
        query = query.filter(Invoice.physical_copy_status == physical_copy_status)

    if date_from is not None:
        query = query.filter(Invoice.document_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.document_date <= date_to)

    if min_total is not None:
        query = query.filter(Invoice.total_gross_amount >= min_total)
    if max_total is not None:
        query = query.filter(Invoice.total_gross_amount <= max_total)

    query = query.order_by(Invoice.document_date.desc(), Invoice.id.desc())
    if limit is not None:
        query = query.limit(limit)

    return query.all()


def list_accounting_years() -> List[int]:
    """Restituisce tutti gli anni contabili presenti (basati su YEAR(document_date)), ordinati in modo decrescente."""
    rows = (
        db.session.query(func.year(Invoice.document_date))
        .filter(Invoice.document_date.isnot(None))
        .distinct()
        .order_by(func.year(Invoice.document_date).desc())
        .all()
    )
    return [row[0] for row in rows]


def filter_invoices_by_date_range(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Invoice]:
    """
    Restituisce le fatture comprese in un intervallo di date (document_date).

    Se uno dei limiti è None, viene ignorato.
    """
    query = Invoice.query

    if date_from is not None:
        query = query.filter(Invoice.document_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.document_date <= date_to)

    query = query.order_by(Invoice.document_date.desc(), Invoice.id.desc())
    return query.all()


def filter_invoices_by_supplier(
    supplier_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Invoice]:
    """
    Restituisce le fatture di un determinato fornitore,
    opzionalmente filtrate per intervallo di date.
    """
    query = Invoice.query.filter_by(supplier_id=supplier_id)

    if date_from is not None:
        query = query.filter(Invoice.document_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.document_date <= date_to)

    query = query.order_by(Invoice.document_date.desc(), Invoice.id.desc())
    return query.all()


def filter_invoices_by_payment_status(
    payment_status: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Invoice]:
    """
    Restituisce le fatture filtrate per stato di pagamento
    (unpaid, partial, paid, ...), opzionalmente per intervallo di date.
    """
    query = Invoice.query.filter_by(payment_status=payment_status)

    if date_from is not None:
        query = query.filter(Invoice.document_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.document_date <= date_to)

    query = query.order_by(Invoice.document_date.asc(), Invoice.id.asc())
    return query.all()


def create_invoice(**kwargs) -> Invoice:
    """
    Crea una nuova fattura e la aggiunge alla sessione.

    Non esegue il commit: questo viene demandato al servizio chiamante.
    """
    if kwargs.get("legal_entity_id") is None:
        raise ValueError("legal_entity_id è obbligatorio per creare una fattura")

    # Rimuovi accounting_year se passato (non è più una colonna del DB)
    kwargs.pop("accounting_year", None)

    invoice = Invoice(**kwargs)
    db.session.add(invoice)
    return invoice


def update_invoice(invoice: Invoice, **kwargs) -> Invoice:
    """
    Aggiorna i campi di una fattura esistente.

    I campi da aggiornare vengono passati come kwargs.
    """
    if "legal_entity_id" in kwargs and kwargs.get("legal_entity_id") is None:
        raise ValueError("legal_entity_id non può essere nullo")

    # Rimuovi accounting_year se passato (non è più una colonna del DB)
    kwargs.pop("accounting_year", None)

    for key, value in kwargs.items():
        if hasattr(invoice, key):
            setattr(invoice, key, value)
    return invoice


def create_invoice_with_details(
    *,
    invoice_dto: InvoiceDTO,
    supplier_id: int,
    legal_entity_id: int,
    import_source: Optional[str] = None,
) -> Tuple[Invoice, bool]:
    """
    Crea una fattura completa di righe, riepiloghi IVA e pagamenti partendo dal DTO.

    Restituisce (invoice, True) se creata, oppure (invoice_esistente, False) se duplicato.
    """
    existing = find_existing_invoice(
        file_name=invoice_dto.file_name,
        file_hash=invoice_dto.file_hash,
    )
    if existing:
        return existing, False

    invoice_kwargs = {
        "supplier_id": supplier_id,
        "legal_entity_id": legal_entity_id,
        "document_number": invoice_dto.invoice_number,
        "invoice_series": invoice_dto.invoice_series,
        "document_date": invoice_dto.invoice_date,
        "registration_date": invoice_dto.registration_date,
        "currency": invoice_dto.currency or "EUR",
        "total_taxable_amount": invoice_dto.total_taxable_amount,
        "total_vat_amount": invoice_dto.total_vat_amount,
        "total_gross_amount": invoice_dto.total_gross_amount,
        "doc_status": invoice_dto.doc_status,
        "payment_status": invoice_dto.payment_status,
        "due_date": invoice_dto.due_date,
        "file_name": invoice_dto.file_name,
        "file_hash": invoice_dto.file_hash,
        "import_source": import_source,
    }

    if not invoice_kwargs["document_number"]:
        raise ValueError("document_number è obbligatorio per creare una fattura")
    if invoice_kwargs["document_date"] is None:
        raise ValueError("document_date è obbligatoria per creare una fattura")
    if not invoice_kwargs["file_name"]:
        raise ValueError("file_name è obbligatorio per tracciare il file XML importato")

    invoice = create_invoice(**invoice_kwargs)
    db.session.flush()  # id necessario per le relazioni figlie

    for line_dto in invoice_dto.lines or []:
        create_invoice_line_from_dto(invoice.id, line_dto)

    for vat_dto in invoice_dto.vat_summaries or []:
        create_vat_summary_from_dto(invoice.id, vat_dto)

    for payment_dto in invoice_dto.payments or []:
        create_payment_from_dto(invoice, payment_dto)

    return invoice, True


def create_invoice_line_from_dto(document_id: int, line_dto: InvoiceLineDTO) -> InvoiceLine:
    """Crea una InvoiceLine partendo dal DTO e la aggiunge alla sessione."""
    description = line_dto.description or "Descrizione non disponibile"
    line = InvoiceLine(
        document_id=document_id,
        line_number=line_dto.line_number,
        description=description,
        quantity=line_dto.quantity,
        unit_of_measure=line_dto.unit_of_measure,
        unit_price=line_dto.unit_price,
        discount_amount=line_dto.discount_amount,
        discount_percent=line_dto.discount_percent,
        taxable_amount=line_dto.taxable_amount,
        vat_rate=line_dto.vat_rate,
        vat_amount=line_dto.vat_amount,
        total_line_amount=line_dto.total_line_amount,
        sku_code=line_dto.sku_code,
        internal_code=line_dto.internal_code,
    )
    db.session.add(line)
    return line


def create_vat_summary_from_dto(document_id: int, vat_dto: VatSummaryDTO) -> VatSummary:
    """Crea un VatSummary partendo dal DTO e lo aggiunge alla sessione."""
    summary = VatSummary(
        document_id=document_id,
        vat_rate=vat_dto.vat_rate,
        taxable_amount=vat_dto.taxable_amount,
        vat_amount=vat_dto.vat_amount,
        nature=vat_dto.nature,
    )
    db.session.add(summary)
    return summary


def create_payment_from_dto(document: Invoice, payment_dto: PaymentDTO) -> Payment:
    """Crea un Payment partendo dal DTO e lo aggiunge alla sessione."""
    payment = Payment(
        document_id=document.id,
        due_date=payment_dto.due_date,
        expected_amount=payment_dto.expected_amount,
        payment_terms=payment_dto.payment_terms,
        payment_method=payment_dto.payment_method,
        status="unpaid",
    )
    db.session.add(payment)

    if document.due_date is None and payment_dto.due_date:
        document.due_date = payment_dto.due_date

    return payment


def get_supplier_account_balance(
    supplier_id: int, legal_entity_id: Optional[int] = None
) -> Dict[str, Decimal | int]:
    """Calcola l'estratto conto di un fornitore, opzionalmente filtrato per legal entity.

    Ritorna un dizionario con:
    - expected_total: totale fatture (expected_amount)
    - paid_total: totale pagato (paid_amount)
    - residual: expected_total - paid_total
    - invoice_count: numero di fatture considerate
    """
    query = (
        db.session.query(
            func.coalesce(func.sum(Invoice.total_gross_amount), 0),
            func.coalesce(func.sum(Payment.paid_amount), 0),
            func.count(func.distinct(Invoice.id)),
        )
        .select_from(Invoice)
        .outerjoin(Payment, Payment.document_id == Invoice.id)
        .filter(Invoice.supplier_id == supplier_id)
    )

    if legal_entity_id is not None:
        query = query.filter(Invoice.legal_entity_id == legal_entity_id)

    expected_total, paid_total, invoice_count = query.one()

    residual = expected_total - paid_total

    return {
        "expected_total": expected_total,
        "paid_total": paid_total,
        "residual": residual,
        "invoice_count": invoice_count,
    }


def list_supplier_legal_entities(
    supplier_id: int,
) -> List[Dict[str, int | str]]:
    """Elenca le società intestatarie collegate al fornitore con conteggio fatture."""
    rows = (
        db.session.query(
            LegalEntity.id.label("id"),
            LegalEntity.name.label("name"),
            func.count(Invoice.id).label("invoice_count"),
        )
        .join(Invoice, Invoice.legal_entity_id == LegalEntity.id)
        .filter(Invoice.supplier_id == supplier_id)
        .group_by(LegalEntity.id, LegalEntity.name)
        .order_by(LegalEntity.name.asc())
        .all()
    )

    return [
        {
            "id": row.id,
            "name": row.name,
            "invoice_count": row.invoice_count,
        }
        for row in rows
    ]
