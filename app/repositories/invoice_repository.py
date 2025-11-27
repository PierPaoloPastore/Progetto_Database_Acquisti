from __future__ import annotations

"""
Repository centralizzato per fatture e relativi record collegati.

Include CRUD per:
- Invoice
- InvoiceLine
- VatSummary
- Payment

e una funzione di convenienza per creare l'intero albero da InvoiceDTO
in modo transazionale (commit demandato al service chiamante).
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app.extensions import db
from app.models import Invoice, InvoiceLine, Payment, VatSummary
from app.parsers.fatturapa_parser import InvoiceDTO, InvoiceLineDTO, PaymentDTO, VatSummaryDTO


# --- Utilità interne ---------------------------------------------------------------

def _compute_accounting_year(
    registration_date: Optional[date], invoice_date: Optional[date]
) -> int:
    """Calcola l'anno contabile con priorità: registrazione, fattura, anno corrente."""
    if registration_date:
        return registration_date.year
    if invoice_date:
        return invoice_date.year
    from datetime import date as _date

    return _date.today().year


# --- Lettura base -----------------------------------------------------------------

def get_invoice_by_id(invoice_id: int) -> Optional[Invoice]:
    """Restituisce una fattura dato il suo ID, oppure None se non trovata."""
    return Invoice.query.get(invoice_id)


def get_invoice_by_file_name(file_name: Optional[str]) -> Optional[Invoice]:
    """Restituisce la fattura associata a un nome file XML, se esiste."""
    if not file_name:
        return None
    return Invoice.query.filter_by(file_name=file_name).first()


def get_invoice_by_file_hash(file_hash: Optional[str]) -> Optional[Invoice]:
    """Restituisce la fattura associata a un hash di file, se esiste."""
    if not file_hash:
        return None
    return Invoice.query.filter_by(file_hash=file_hash).first()


def find_existing_invoice(*, file_name: Optional[str] = None, file_hash: Optional[str] = None) -> Optional[Invoice]:
    """Utility: cerca una fattura esistente per file_name o file_hash."""
    invoice = get_invoice_by_file_name(file_name)
    if invoice is not None:
        return invoice
    return get_invoice_by_file_hash(file_hash)


def list_invoices(
    *,
    legal_entity_id: Optional[int] = None,
    accounting_year: Optional[int] = None,
    limit: int = 200,
) -> List[Invoice]:
    """Restituisce una lista di fatture ordinate per data e ID decrescente."""
    query = Invoice.query
    if legal_entity_id is not None:
        query = query.filter(Invoice.legal_entity_id == legal_entity_id)
    if accounting_year is not None:
        query = query.filter(Invoice.accounting_year == accounting_year)
    query = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def search_invoices_by_filters(
    *,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    supplier_id: Optional[int] = None,
    payment_status: Optional[str] = None,
    legal_entity_id: Optional[int] = None,
    accounting_year: Optional[int] = None,
    min_total: Optional[Decimal] = None,
    max_total: Optional[Decimal] = None,
    limit: int = 200,
) -> List[Invoice]:
    """Applica filtri combinati per la ricerca fatture."""
    query = Invoice.query

    if legal_entity_id is not None:
        query = query.filter(Invoice.legal_entity_id == legal_entity_id)
    if accounting_year is not None:
        query = query.filter(Invoice.accounting_year == accounting_year)
    if supplier_id is not None:
        query = query.filter(Invoice.supplier_id == supplier_id)
    if payment_status is not None:
        query = query.filter(Invoice.payment_status == payment_status)
    if date_from is not None:
        query = query.filter(Invoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.invoice_date <= date_to)
    if min_total is not None:
        query = query.filter(Invoice.total_gross_amount >= min_total)
    if max_total is not None:
        query = query.filter(Invoice.total_gross_amount <= max_total)

    query = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def list_accounting_years() -> List[int]:
    """Restituisce gli anni contabili disponibili (distinct) in ordine decrescente."""
    years = (
        Invoice.query.with_entities(Invoice.accounting_year)
        .filter(Invoice.accounting_year.isnot(None))
        .distinct()
        .order_by(Invoice.accounting_year.desc())
        .all()
    )
    return [year[0] for year in years if year[0] is not None]


def filter_invoices_by_date_range(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Invoice]:
    """Restituisce le fatture comprese in un intervallo di date (invoice_date)."""
    query = Invoice.query

    if date_from is not None:
        query = query.filter(Invoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.invoice_date <= date_to)

    query = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    return query.all()


def filter_invoices_by_supplier(
    supplier_id: int,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Invoice]:
    """Restituisce le fatture di un determinato fornitore (opzionalmente per data)."""
    query = Invoice.query.filter_by(supplier_id=supplier_id)

    if date_from is not None:
        query = query.filter(Invoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.invoice_date <= date_to)

    query = query.order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    return query.all()


def filter_invoices_by_payment_status(
    payment_status: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Invoice]:
    """Restituisce le fatture filtrate per stato pagamento (opz. con range date)."""
    query = Invoice.query.filter_by(payment_status=payment_status)

    if date_from is not None:
        query = query.filter(Invoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.invoice_date <= date_to)

    query = query.order_by(Invoice.invoice_date.asc(), Invoice.id.asc())
    return query.all()


def get_supplier_account_balance(
    supplier_id: int, legal_entity_id: Optional[int] = None
) -> Dict[str, Decimal | int]:
    """
    Calcola un estratto conto sintetico per un fornitore:
    - expected_total: somma dei totali lordi fattura
    - paid_total: somma importi pagati
    - residual: expected_total - paid_total
    - invoice_count: numero di fatture considerate

    Il filtro per legal_entity_id � opzionale.
    """
    invoice_query = Invoice.query.filter(Invoice.supplier_id == supplier_id)
    if legal_entity_id is not None:
        invoice_query = invoice_query.filter(Invoice.legal_entity_id == legal_entity_id)

    invoice_count = invoice_query.count()

    expected_total = (
        invoice_query.with_entities(
            db.func.coalesce(db.func.sum(Invoice.total_gross_amount), 0)
        ).scalar()
        or Decimal("0")
    )

    payments_sum_query = (
        db.session.query(db.func.coalesce(db.func.sum(Payment.paid_amount), 0))
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .filter(Invoice.supplier_id == supplier_id)
    )
    if legal_entity_id is not None:
        payments_sum_query = payments_sum_query.filter(Invoice.legal_entity_id == legal_entity_id)

    paid_total = payments_sum_query.scalar() or Decimal("0")
    residual = expected_total - paid_total

    return {
        "expected_total": expected_total,
        "paid_total": paid_total,
        "residual": residual,
        "invoice_count": invoice_count,
    }


# --- Creazione / aggiornamento base ----------------------------------------------

def create_invoice(**kwargs) -> Invoice:
    """
    Crea una nuova fattura e la aggiunge alla sessione (senza commit).
    """
    registration_date = kwargs.get("registration_date")
    invoice_date = kwargs.get("invoice_date")
    if "accounting_year" not in kwargs:
        kwargs["accounting_year"] = _compute_accounting_year(
            registration_date, invoice_date
        )
    if kwargs.get("legal_entity_id") is None:
        raise ValueError("legal_entity_id è obbligatorio per creare una fattura")

    invoice = Invoice(**kwargs)
    db.session.add(invoice)
    return invoice


def update_invoice(invoice: Invoice, **kwargs) -> Invoice:
    """Aggiorna i campi di una fattura esistente."""
    registration_date = kwargs.get("registration_date", invoice.registration_date)
    invoice_date = kwargs.get("invoice_date", invoice.invoice_date)
    if "accounting_year" not in kwargs:
        kwargs["accounting_year"] = _compute_accounting_year(
            registration_date, invoice_date
        )
    if "legal_entity_id" in kwargs and kwargs.get("legal_entity_id") is None:
        raise ValueError("legal_entity_id non può essere nullo")

    for key, value in kwargs.items():
        if hasattr(invoice, key):
            setattr(invoice, key, value)
    return invoice


def create_invoice_line(**kwargs) -> InvoiceLine:
    """Crea una riga fattura e la aggiunge alla sessione (senza commit)."""
    line = InvoiceLine(**kwargs)
    db.session.add(line)
    return line


def update_invoice_line(line: InvoiceLine, **kwargs) -> InvoiceLine:
    """Aggiorna i campi di una riga fattura esistente."""
    for key, value in kwargs.items():
        if hasattr(line, key):
            setattr(line, key, value)
    return line


def list_lines_by_invoice(invoice_id: int) -> List[InvoiceLine]:
    """Restituisce tutte le righe associate a una fattura."""
    return (
        InvoiceLine.query.filter_by(invoice_id=invoice_id)
        .order_by(InvoiceLine.line_number.asc().nullslast())
        .all()
    )


def list_lines_by_category(category_id: int) -> List[InvoiceLine]:
    """Restituisce tutte le righe associate a una determinata categoria gestionale."""
    return (
        InvoiceLine.query.filter_by(category_id=category_id)
        .order_by(InvoiceLine.invoice_id.asc(), InvoiceLine.line_number.asc())
        .all()
    )


def create_vat_summary(**kwargs) -> VatSummary:
    """Crea un riepilogo IVA e lo aggiunge alla sessione (senza commit)."""
    summary = VatSummary(**kwargs)
    db.session.add(summary)
    return summary


def list_vat_summaries_by_invoice(invoice_id: int) -> List[VatSummary]:
    """Restituisce tutti i riepiloghi IVA associati a una fattura."""
    return (
        VatSummary.query.filter_by(invoice_id=invoice_id)
        .order_by(VatSummary.vat_rate.asc())
        .all()
    )


def create_payment(**kwargs) -> Payment:
    """Crea un pagamento/scadenza e lo aggiunge alla sessione (senza commit)."""
    payment = Payment(**kwargs)
    db.session.add(payment)
    return payment


def get_payment_by_id(payment_id: int) -> Optional[Payment]:
    """Restituisce un pagamento dato il suo ID."""
    return Payment.query.get(payment_id)


def update_payment(payment: Payment, **kwargs) -> Payment:
    """Aggiorna i campi di un pagamento esistente."""
    for key, value in kwargs.items():
        if hasattr(payment, key):
            setattr(payment, key, value)
    return payment


def list_payments_by_invoice(invoice_id: int) -> List[Payment]:
    """Restituisce tutti i pagamenti associati a una fattura."""
    return (
        Payment.query.filter_by(invoice_id=invoice_id)
        .order_by(Payment.due_date.asc().nullslast())
        .all()
    )


def list_overdue_payments(reference_date: Optional[date] = None) -> List[Payment]:
    """Restituisce i pagamenti scaduti e non completamente saldati."""
    if reference_date is None:
        from datetime import date as _date

        reference_date = _date.today()

    query = Payment.query.filter(
        Payment.due_date.isnot(None),
        Payment.due_date < reference_date,
        Payment.status != "paid",
    ).order_by(Payment.due_date.asc())

    return query.all()


# --- Creazione albero da DTO ------------------------------------------------------

def create_invoice_with_details(
    invoice_dto: InvoiceDTO,
    supplier_id: int,
    legal_entity_id: int,
    import_source: Optional[str] = None,
) -> Tuple[Invoice, bool]:
    """
    Crea fattura + righe + riepiloghi IVA + pagamenti da un InvoiceDTO.

    Restituisce (invoice, created_flag). Se esiste già (file_name/file_hash) restituisce
    l'esistente con created_flag=False senza creare nulla.
    """
    if legal_entity_id is None:
        raise ValueError("legal_entity_id è obbligatorio per creare una fattura")

    existing = find_existing_invoice(
        file_name=invoice_dto.file_name,
        file_hash=invoice_dto.file_hash,
    )
    if existing is not None:
        return existing, False

    accounting_year = _compute_accounting_year(
        invoice_dto.registration_date, invoice_dto.invoice_date
    )

    invoice = Invoice(
        supplier_id=supplier_id,
        legal_entity_id=legal_entity_id,
        invoice_number=invoice_dto.invoice_number,
        invoice_series=invoice_dto.invoice_series,
        invoice_date=invoice_dto.invoice_date,
        registration_date=invoice_dto.registration_date,
        currency=invoice_dto.currency,
        total_taxable_amount=invoice_dto.total_taxable_amount,
        total_vat_amount=invoice_dto.total_vat_amount,
        total_gross_amount=invoice_dto.total_gross_amount,
        accounting_year=accounting_year,
        doc_status=invoice_dto.doc_status,
        payment_status=invoice_dto.payment_status,
        due_date=invoice_dto.due_date,
        file_name=invoice_dto.file_name or "",
        file_hash=invoice_dto.file_hash,
        import_source=import_source,
        notes_internal=None,
    )
    db.session.add(invoice)
    # flush immediato per avere invoice.id disponibile nelle relazioni figlie
    db.session.flush()

    _create_lines_from_dto(invoice, invoice_dto.lines)
    _create_vat_summaries_from_dto(invoice, invoice_dto.vat_summaries)
    _create_payments_from_dto(invoice, invoice_dto.payments)

    db.session.flush()
    return invoice, True


def _create_lines_from_dto(invoice: Invoice, lines: List[InvoiceLineDTO]) -> None:
    for line_dto in lines:
        create_invoice_line(
            invoice=invoice,
            category_id=None,
            line_number=line_dto.line_number,
            description=line_dto.description or "",
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


def _create_vat_summaries_from_dto(invoice: Invoice, vat_summaries: List[VatSummaryDTO]) -> None:
    for summary_dto in vat_summaries:
        create_vat_summary(
            invoice=invoice,
            vat_rate=summary_dto.vat_rate,
            taxable_amount=summary_dto.taxable_amount,
            vat_amount=summary_dto.vat_amount,
            nature=summary_dto.nature,
        )


def _create_payments_from_dto(invoice: Invoice, payments: List[PaymentDTO]) -> None:
    for payment_dto in payments:
        create_payment(
            invoice=invoice,
            due_date=payment_dto.due_date,
            expected_amount=payment_dto.expected_amount,
            payment_terms=payment_dto.payment_terms,
            payment_method=payment_dto.payment_method,
            paid_date=None,
            paid_amount=None,
            status="unpaid",
            notes=None,
        )
