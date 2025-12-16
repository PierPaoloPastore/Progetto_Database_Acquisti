"""
Servizi per la gestione dei pagamenti (Payment).
Rifattorizzato con Pattern Unit of Work.
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional, Sequence

from werkzeug.utils import secure_filename

from app.models import Document, Payment, PaymentDocument
from app.services import scan_service, settings_service
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
            expected_amount=amount,
            due_date=payment_date,
            notes=description,
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


def create_batch_payment(
    file,
    allocations: Sequence[dict],
    method: Optional[str],
    notes: Optional[str],
) -> PaymentDocument:
    """Crea un pagamento cumulativo collegato a più scadenze."""
    if not allocations:
        raise ValueError("Nessuna allocazione fornita per il pagamento cumulativo.")

    today = date.today()

    with UnitOfWork() as uow:
        # Gestione file allegato
        if file:
            base_path = settings_service.get_payment_files_storage_path()
            safe_name = secure_filename(file.filename) or f"batch_payment_{today.isoformat()}"
            relative_path = scan_service.store_payment_document_file(
                file=file,
                base_path=base_path,
                filename=safe_name,
            )
            file_name = safe_name
            file_path = relative_path
        else:
            placeholder_name = f"batch_payment_{today.isoformat()}"
            file_name = placeholder_name
            file_path = placeholder_name

        payment_document = PaymentDocument(
            file_name=file_name,
            file_path=file_path,
            payment_type=method or "batch",
            status="reconciled",
        )
        uow.session.add(payment_document)
        uow.session.flush()

        touched_documents = set()

        for allocation in allocations:
            payment_id = allocation.get("payment_id")
            amount = allocation.get("amount")
            if payment_id is None or amount is None:
                continue

            payment = uow.payments.get_by_id(int(payment_id))
            if not payment:
                raise ValueError(f"Pagamento con id {payment_id} non trovato")

            increment = Decimal(str(amount))
            current_paid = Decimal(payment.paid_amount or 0)
            new_paid = current_paid + increment

            expected_amount = Decimal(payment.expected_amount or 0)
            payment_status = "partial"
            if expected_amount and new_paid >= expected_amount:
                payment_status = "paid"

            payment.status = payment_status
            payment.paid_date = today
            payment.paid_amount = new_paid
            payment.payment_method = method
            payment.notes = notes
            payment.payment_document = payment_document

            touched_documents.add(payment.document_id)

        for document_id in touched_documents:
            document = uow.session.query(Document).get(document_id)
            if not document:
                continue

            related_payments = uow.payments.get_by_document_id(document_id)
            document.is_paid = all(p.status == "paid" for p in related_payments)

        uow.commit()

        return payment_document

def create_batch_payment_from_documents(
    file,
    document_allocations: List[dict],
    method: Optional[str],
    notes: Optional[str],
) -> dict:
    """
    Process batch payment for multiple documents.
    Auto-creates Payment records if they don't exist.

    Args:
        file: Uploaded PDF file (or None)
        document_allocations: List of dicts with document_id and amount
        method: Payment method
        notes: Optional notes

    Returns:
        Dict with success_count, error_count, and results list
    """
    if not document_allocations:
        raise ValueError("Nessuna allocazione fornita per il pagamento cumulativo.")

    today = date.today()
    results = []

    with UnitOfWork() as uow:
        # Step 1: Create PaymentDocument if file provided
        payment_document = None
        if file and file.filename:
            base_path = settings_service.get_payment_files_storage_path()
            safe_name = secure_filename(file.filename) or f"batch_payment_{today.isoformat()}"
            relative_path = scan_service.store_payment_document_file(
                file=file,
                base_path=base_path,
                filename=safe_name,
            )
            payment_document = PaymentDocument(
                file_name=safe_name,
                file_path=relative_path,
                payment_type=method or "batch",
                status="reconciled",
            )
        else:
            placeholder_name = f"batch_payment_{today.isoformat()}"
            payment_document = PaymentDocument(
                file_name=placeholder_name,
                file_path=placeholder_name,
                payment_type=method or "batch",
                status="reconciled",
            )

        uow.session.add(payment_document)
        uow.session.flush()

        # Step 2: Get all Document IDs
        doc_ids = [alloc["document_id"] for alloc in document_allocations]

        # Step 3: Fetch all Payment records for these Documents
        payment_map = {}  # {document_id: [Payment, ...]}
        payments = uow.payments.get_unpaid_by_document_ids(doc_ids)
        for payment in payments:
            if payment.document_id not in payment_map:
                payment_map[payment.document_id] = []
            payment_map[payment.document_id].append(payment)

        touched_documents = set()

        # Step 4: Process each document allocation
        for alloc in document_allocations:
            doc_id = alloc["document_id"]
            amount = alloc["amount"]

            try:
                # Get or create Payment record
                if doc_id not in payment_map or len(payment_map[doc_id]) == 0:
                    # Auto-create Payment record (edge case handling)
                    document = uow.session.query(Document).get(doc_id)
                    if not document:
                        results.append({
                            "document_id": doc_id,
                            "success": False,
                            "error": "Documento non trovato"
                        })
                        continue

                    payment = Payment(
                        document_id=doc_id,
                        due_date=document.due_date or today,
                        expected_amount=Decimal(str(amount)),
                        status='unpaid',
                        supplier_id=document.supplier_id
                    )
                    uow.payments.add(payment)
                    uow.session.flush()
                else:
                    # Use first unpaid/partial Payment
                    payment = payment_map[doc_id][0]

                # Update Payment record
                increment = Decimal(str(amount))
                current_paid = Decimal(payment.paid_amount or 0)
                new_paid = current_paid + increment

                payment.paid_date = today
                payment.paid_amount = new_paid
                payment.payment_method = method
                payment.notes = notes
                payment.payment_document = payment_document

                # Set status
                expected_amount = Decimal(payment.expected_amount or 0)
                if expected_amount and new_paid >= expected_amount:
                    payment.status = 'paid'
                else:
                    payment.status = 'partial'

                touched_documents.add(doc_id)

                results.append({
                    "document_id": doc_id,
                    "success": True,
                    "payment_id": payment.id
                })

            except Exception as e:
                logger.error(f"Failed to process payment for doc {doc_id}: {e}")
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(e)
                })

        # Step 5: Update Document.is_paid flags
        for document_id in touched_documents:
            document = uow.session.query(Document).get(document_id)
            if document:
                related_payments = uow.payments.get_by_document_id(document_id)
                document.is_paid = all(p.status == 'paid' for p in related_payments)

        uow.commit()

    success_count = len([r for r in results if r['success']])
    error_count = len([r for r in results if not r['success']])

    return {
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }

def _update_document_paid_status(uow: UnitOfWork, document: Document):
    """
    Helper interno: ricalcola se la fattura è pagata totalmente.
    """
    payments = uow.payments.get_by_document_id(document.id)
    total_paid = sum(p.expected_amount for p in payments)

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