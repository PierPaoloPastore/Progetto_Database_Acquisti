"""
Repository per il modello Payment.

Gestisce le operazioni di lettura/creazione/aggiornamento dei pagamenti/scadenze.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from app.extensions import db
from app.models import Invoice, Payment, PaymentDocument
from sqlalchemy.orm import joinedload


def get_payment_by_id(payment_id: int) -> Optional[Payment]:
    """Restituisce un pagamento dato il suo ID, oppure None se non trovato."""
    return Payment.query.get(payment_id)


def list_payments_by_invoice(document_id: int) -> List[Payment]:
    """Restituisce tutti i pagamenti associati a un documento."""
    return (
        Payment.query.filter_by(document_id=document_id)
        .order_by(Payment.due_date.asc().nullslast())
        .all()
    )


def list_overdue_payments(reference_date: Optional[date] = None) -> List[Payment]:
    """
    Restituisce i pagamenti scaduti e non completamente saldati.

    :param reference_date: data di riferimento; se None usa la data odierna.
    """
    if reference_date is None:
        reference_date = date.today()

    query = Payment.query.filter(
        Payment.due_date.isnot(None),
        Payment.due_date < reference_date,
        Payment.status != "paid",
    ).order_by(Payment.due_date.asc())

    return query.all()


def update_payment(payment: Payment, **kwargs) -> Payment:
    """
    Aggiorna i campi di un pagamento esistente.

    I campi da aggiornare vengono passati come kwargs.
    """
    for key, value in kwargs.items():
        if hasattr(payment, key):
            setattr(payment, key, value)
    return payment


def create_payment_document(**kwargs) -> PaymentDocument:
    """Crea un nuovo documento di pagamento senza eseguire il commit."""

    document = PaymentDocument(**kwargs)
    db.session.add(document)
    return document


def get_payment_document(document_id: int) -> Optional[PaymentDocument]:
    """Recupera un PaymentDocument includendo i pagamenti correlati."""

    return (
        PaymentDocument.query.options(joinedload(PaymentDocument.payments))
        .filter_by(id=document_id)
        .first()
    )


def list_payment_documents_by_status(statuses: List[str]) -> List[PaymentDocument]:
    """Ritorna i documenti filtrati per stato."""

    if not statuses:
        return []

    return (
        PaymentDocument.query.filter(PaymentDocument.status.in_(statuses))
        .order_by(PaymentDocument.uploaded_at.desc())
        .all()
    )


def create_payment(
    document: Invoice,
    amount: Decimal,
    payment_document: Optional[PaymentDocument] = None,
    **kwargs,
) -> Payment:
    """
    Crea un pagamento collegato a un documento e opzionalmente a un documento di pagamento.

    Nota: per il calcolo dei saldi viene usato ``paid_amount`` come importo
    effettivamente pagato.
    """

    payment = Payment(
        document_id=document.id,
        paid_amount=amount,
        payment_document=payment_document,
        **kwargs,
    )
    db.session.add(payment)
    return payment


def list_payments_for_invoice(document_id: int) -> List[Payment]:
    """Lista dei pagamenti associati a un documento."""

    return Payment.query.filter_by(document_id=document_id).all()


def sum_payments_for_invoice(document_id: int) -> Decimal:
    """Somma gli importi pagati per un documento (campo ``paid_amount``)."""

    total = (
        db.session.query(db.func.coalesce(db.func.sum(Payment.paid_amount), 0))
        .filter(Payment.document_id == document_id)
        .scalar()
    )
    return Decimal(total)
