"""
Repository per il modello Invoice.

Contiene funzioni di utilità per accedere e manipolare le fatture.
"""

from datetime import date
from typing import List, Optional

from app.extensions import db
from app.models import Invoice


def get_invoice_by_id(invoice_id: int) -> Optional[Invoice]:
    """Restituisce una fattura dato il suo ID, oppure None se non trovata."""
    return Invoice.query.get(invoice_id)


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


def list_invoices(limit: int = 200) -> List[Invoice]:
    """
    Restituisce una lista di fatture ordinate per data e ID decrescente.

    :param limit: massimo numero di record da restituire.
    """
    query = Invoice.query.order_by(
        Invoice.invoice_date.desc(),
        Invoice.id.desc(),
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def filter_invoices_by_date_range(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> List[Invoice]:
    """
    Restituisce le fatture comprese in un intervallo di date (invoice_date).

    Se uno dei limiti è None, viene ignorato.
    """
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
    """
    Restituisce le fatture di un determinato fornitore,
    opzionalmente filtrate per intervallo di date.
    """
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
    """
    Restituisce le fatture filtrate per stato di pagamento
    (unpaid, partial, paid, ...), opzionalmente per intervallo di date.
    """
    query = Invoice.query.filter_by(payment_status=payment_status)

    if date_from is not None:
        query = query.filter(Invoice.invoice_date >= date_from)
    if date_to is not None:
        query = query.filter(Invoice.invoice_date <= date_to)

    query = query.order_by(Invoice.invoice_date.asc(), Invoice.id.asc())
    return query.all()


def create_invoice(**kwargs) -> Invoice:
    """
    Crea una nuova fattura e la aggiunge alla sessione.

    Non esegue il commit: questo viene demandato al servizio chiamante
    (ad esempio import_service o invoice_service).
    """
    invoice = Invoice(**kwargs)
    db.session.add(invoice)
    return invoice


def update_invoice(invoice: Invoice, **kwargs) -> Invoice:
    """
    Aggiorna i campi di una fattura esistente.

    I campi da aggiornare vengono passati come kwargs.
    """
    for key, value in kwargs.items():
        if hasattr(invoice, key):
            setattr(invoice, key, value)
    return invoice
