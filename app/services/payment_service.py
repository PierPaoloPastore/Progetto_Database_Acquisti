"""
Servizi per la gestione dei pagamenti (Payment).
Rifattorizzato con Pattern Unit of Work.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from app.models import Payment, Document
from app.services.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)

def list_payments_by_document(document_id: int) -> List[Payment]:
    """Restituisce i pagamenti di una specifica fattura."""
    with UnitOfWork() as uow:
        return uow.payments.get_by_document_id(document_id)

def add_payment(
    document_id: int,
    amount: float,
    payment_date: date,
    description: Optional[str] = None
) -> Payment:
    """
    Registra un nuovo pagamento e aggiorna lo stato della fattura.
    """
    with UnitOfWork() as uow:
        # 1. Recupera il documento (usando sessione UoW per coerenza)
        document = uow.session.query(Document).get(document_id)
        if not document:
            raise ValueError(f"Documento con id {document_id} non trovato")

        # 2. Crea il pagamento
        payment = Payment(
            document_id=document_id,
            amount=amount,
            payment_date=payment_date,
            description=description,
            supplier_id=document.supplier_id # Denormalizzazione utile
        )
        uow.payments.add(payment)
        
        # Flush per assicurare che il pagamento sia visibile per i calcoli successivi
        uow.session.flush()

        # 3. Aggiorna stato pagato del documento
        _update_document_paid_status(uow, document)

        uow.commit()
        
        logger.info(f"Pagamento di {amount} aggiunto al doc {document_id}")
        return payment

def delete_payment(payment_id: int) -> bool:
    """
    Cancella un pagamento e ricalcola lo stato della fattura.
    """
    with UnitOfWork() as uow:
        payment = uow.payments.get_by_id(payment_id)
        if not payment:
            return False

        document_id = payment.document_id
        
        # 1. Cancella pagamento
        uow.payments.delete(payment)
        uow.session.flush()

        # 2. Recupera documento e aggiorna stato
        document = uow.session.query(Document).get(document_id)
        if document:
            _update_document_paid_status(uow, document)

        uow.commit()
        
        logger.info(f"Pagamento {payment_id} cancellato")
        return True

def _update_document_paid_status(uow: UnitOfWork, document: Document):
    """
    Helper interno: ricalcola se la fattura è pagata totalmente.
    """
    payments = uow.payments.get_by_document_id(document.id)
    total_paid = sum(p.amount for p in payments)
    
    # Tolleranza per virgola mobile
    if total_paid >= (float(document.total_gross_amount or 0) - 0.01):
        document.is_paid = True
    else:
        document.is_paid = False

# --- FUNZIONE REINSERITA PER COMPATIBILITÀ DASHBOARD ---
def list_overdue_payments_for_ui() -> List[Document]:
    """
    Restituisce l'elenco delle fatture scadute e non pagate.
    Usato nella dashboard.
    """
    with UnitOfWork() as uow:
        today = date.today()
        # Nota: Interroghiamo Document, non Payment, ma concettualmente è legato ai pagamenti mancanti
        overdue_invoices = (
            uow.session.query(Document)
            .filter(
                Document.document_type == 'invoice',
                Document.is_paid == False,
                Document.due_date != None,
                Document.due_date < today
            )
            .order_by(Document.due_date.asc())
            .all()
        )
        return overdue_invoices