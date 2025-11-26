"""
Repository per il modello Payment.

Gestisce le operazioni di lettura/creazione/aggiornamento dei pagamenti/scadenze.
"""

from datetime import date
from typing import List, Optional

from app.extensions import db
from app.models import Payment


def get_payment_by_id(payment_id: int) -> Optional[Payment]:
    """Restituisce un pagamento dato il suo ID, oppure None se non trovato."""
    return Payment.query.get(payment_id)


def list_payments_by_invoice(invoice_id: int) -> List[Payment]:
    """Restituisce tutti i pagamenti associati a una fattura."""
    return (
        Payment.query.filter_by(invoice_id=invoice_id)
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


def create_payment(**kwargs) -> Payment:
    """
    Crea un nuovo pagamento/scadenza e lo aggiunge alla sessione.

    Non esegue il commit.
    """
    payment = Payment(**kwargs)
    db.session.add(payment)
    return payment


def update_payment(payment: Payment, **kwargs) -> Payment:
    """
    Aggiorna i campi di un pagamento esistente.

    I campi da aggiornare vengono passati come kwargs.
    """
    for key, value in kwargs.items():
        if hasattr(payment, key):
            setattr(payment, key, value)
    return payment
