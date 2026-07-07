"""
Servizi per la gestione dei pagamenti (Payment).
Rifattorizzato con Pattern Unit of Work.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Sequence

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename

from app.models import CreditNoteAllocation, Document, Payment, PaymentDocument
from app.services import scan_service, settings_service
from app.services.bank_account_service import normalize_iban
from app.services.dto import PaymentHistoryFilters
from app.services.payment_method_catalog import (
    is_known_payment_method,
    is_physical_copy_required,
    normalize_payment_method_code,
    resolve_payment_document_type,
)
from app.services.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


_DECIMAL_ZERO = Decimal("0.00")
_DUPLICATE_PAYMENT_WINDOW_SECONDS = 15


class DuplicatePaymentSubmissionError(ValueError):
    """Segnala un submit di pagamento probabilmente gia registrato."""


def _to_decimal(value) -> Decimal:
    if value in (None, ""):
        return _DECIMAL_ZERO
    try:
        return Decimal(str(value))
    except Exception:
        return _DECIMAL_ZERO


def _is_credit_note_document(document: Optional[Document]) -> bool:
    if document is None:
        return False
    return (getattr(document, "document_type", None) or "").strip().lower() == "credit_note"


def _quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _same_optional_text(left: Optional[str], right: Optional[str]) -> bool:
    return (left or "").strip() == (right or "").strip()


def _has_recent_duplicate_payment_submission(
    uow: UnitOfWork,
    *,
    document_amounts: dict[int, Decimal],
    paid_date: date,
    method: Optional[str],
    bank_account_iban: Optional[str],
) -> bool:
    """Rileva un pagamento uguale registrato pochi secondi prima."""
    bank_doc_amounts = {
        document_id: _quantize_amount(amount)
        for document_id, amount in document_amounts.items()
        if _quantize_amount(amount) > _DECIMAL_ZERO
    }
    if not bank_doc_amounts:
        return False

    since = datetime.utcnow() - timedelta(seconds=_DUPLICATE_PAYMENT_WINDOW_SECONDS)
    recent_payments = uow.payments.list_recent_paid_by_documents(
        list(bank_doc_amounts.keys()),
        paid_date=paid_date,
        since=since,
    )
    recent_by_doc: dict[int, list[Payment]] = {}
    for payment in recent_payments:
        recent_by_doc.setdefault(payment.document_id, []).append(payment)

    for document_id, requested_amount in bank_doc_amounts.items():
        matching_payment = False
        for payment in recent_by_doc.get(document_id, []):
            if method and payment.payment_method != method:
                continue
            payment_document = payment.payment_document
            if not _same_optional_text(
                bank_account_iban,
                payment_document.bank_account_iban if payment_document else None,
            ):
                continue
            if _quantize_amount(_to_decimal(payment.paid_amount)) >= requested_amount:
                matching_payment = True
                break
        if not matching_payment:
            return False

    return True


def _has_recent_duplicate_credit_allocation(
    uow: UnitOfWork,
    *,
    invoice_document_ids: Sequence[int],
    credit_note_document_ids: Sequence[int],
) -> bool:
    if not invoice_document_ids or not credit_note_document_ids:
        return False
    since = datetime.utcnow() - timedelta(seconds=_DUPLICATE_PAYMENT_WINDOW_SECONDS)
    recent_allocations = uow.credit_note_allocations.list_recent_by_documents(
        invoice_document_ids=list(invoice_document_ids),
        credit_note_document_ids=list(credit_note_document_ids),
        since=since,
    )
    return bool(recent_allocations)


def _get_document_payment_totals(
    uow: UnitOfWork,
    document_ids: Sequence[int],
) -> tuple[dict[int, list[tuple[str, Decimal]]], dict[int, Decimal], dict[int, Decimal]]:
    doc_ids = [doc_id for doc_id in document_ids if doc_id]
    if not doc_ids:
        return {}, {}, {}

    rows = (
        uow.session.query(
            Payment.document_id,
            Payment.status,
            Payment.paid_amount,
        )
        .filter(Payment.document_id.in_(doc_ids))
        .all()
    )

    payments_by_document: dict[int, list[tuple[str, Decimal]]] = {}
    for document_id, status, paid_amount in rows:
        payments_by_document.setdefault(document_id, []).append(
            ((status or "").strip().lower(), _to_decimal(paid_amount))
        )

    allocated_in = uow.credit_note_allocations.get_allocated_totals_by_invoice_ids(doc_ids)
    allocated_out = uow.credit_note_allocations.get_allocated_totals_by_credit_note_ids(doc_ids)
    return payments_by_document, allocated_in, allocated_out


def _calculate_document_settlement_snapshot(
    *,
    document: Document,
    payment_rows: Sequence[tuple[str, Decimal]],
    allocated_in: Decimal = _DECIMAL_ZERO,
    allocated_out: Decimal = _DECIMAL_ZERO,
) -> dict[str, Decimal | str]:
    gross_amount = _quantize_amount(_to_decimal(document.total_gross_amount or 0))
    bank_paid_amount = _quantize_amount(sum((amount for _, amount in payment_rows), _DECIMAL_ZERO))
    allocated_in = _quantize_amount(allocated_in)
    allocated_out = _quantize_amount(allocated_out)

    if _is_credit_note_document(document):
        total_credit_amount = _quantize_amount(abs(gross_amount))
        used_amount = allocated_out
        remaining_amount = _quantize_amount(gross_amount + used_amount)
        if total_credit_amount <= _DECIMAL_ZERO:
            overview_status = "paid"
        elif used_amount >= total_credit_amount:
            overview_status = "paid"
        elif used_amount > _DECIMAL_ZERO:
            overview_status = "partial"
        else:
            overview_status = "unpaid"
        return {
            "gross_amount": gross_amount,
            "bank_paid_amount": bank_paid_amount,
            "allocated_amount": used_amount,
            "settled_amount": used_amount,
            "remaining_amount": remaining_amount,
            "overview_status": overview_status,
            "available_credit_amount": _quantize_amount(abs(remaining_amount)),
        }

    settled_amount = _quantize_amount(bank_paid_amount + allocated_in)
    remaining_amount = _quantize_amount(gross_amount - settled_amount)
    if remaining_amount < _DECIMAL_ZERO:
        remaining_amount = _DECIMAL_ZERO

    if gross_amount <= _DECIMAL_ZERO:
        overview_status = "paid"
    elif settled_amount >= gross_amount:
        overview_status = "paid"
    elif bank_paid_amount > _DECIMAL_ZERO or allocated_in > _DECIMAL_ZERO:
        overview_status = "partial"
    else:
        overview_status = "unpaid"

    return {
        "gross_amount": gross_amount,
        "bank_paid_amount": bank_paid_amount,
        "allocated_amount": allocated_in,
        "settled_amount": settled_amount,
        "remaining_amount": remaining_amount,
        "overview_status": overview_status,
        "available_credit_amount": _DECIMAL_ZERO,
    }


def _apply_document_runtime_amounts(document: Document, snapshot: dict[str, Decimal | str]) -> None:
    document.bank_paid_amount = float(snapshot["bank_paid_amount"])
    document.credit_note_allocated_amount = float(snapshot["allocated_amount"])
    document.paid_amount = float(snapshot["settled_amount"])
    document.remaining_amount = float(snapshot["remaining_amount"])
    document.payment_overview_status = str(snapshot["overview_status"])
    if _is_credit_note_document(document):
        document.credit_note_used_amount = float(snapshot["allocated_amount"])
        document.credit_note_available_amount = float(snapshot["available_credit_amount"])


def _allocate_credit_note_amounts(
    *,
    uow: UnitOfWork,
    credit_notes: Sequence[Document],
    invoice_balances: dict[int, Decimal],
    notes: Optional[str] = None,
) -> tuple[dict[int, Decimal], dict[int, Decimal], Decimal]:
    allocations_by_invoice: dict[int, Decimal] = {invoice_id: _DECIMAL_ZERO for invoice_id in invoice_balances}
    allocations_by_credit_note: dict[int, Decimal] = {credit_note.id: _DECIMAL_ZERO for credit_note in credit_notes}
    total_allocated = _DECIMAL_ZERO
    note_text = (notes or "").strip() or None

    if not credit_notes:
        return allocations_by_invoice, allocations_by_credit_note, total_allocated

    existing_totals = uow.credit_note_allocations.get_allocated_totals_by_credit_note_ids([doc.id for doc in credit_notes])
    ordered_invoice_ids = [invoice_id for invoice_id, amount in invoice_balances.items() if amount > _DECIMAL_ZERO]

    for credit_note in credit_notes:
        total_credit = _quantize_amount(abs(_to_decimal(credit_note.total_gross_amount or 0)))
        already_allocated = _quantize_amount(existing_totals.get(credit_note.id, _DECIMAL_ZERO))
        remaining_credit = _quantize_amount(total_credit - already_allocated)
        if remaining_credit <= _DECIMAL_ZERO:
            continue

        for invoice_id in ordered_invoice_ids:
            invoice_remaining = _quantize_amount(invoice_balances.get(invoice_id, _DECIMAL_ZERO))
            if invoice_remaining <= _DECIMAL_ZERO:
                continue
            allocation_amount = _quantize_amount(min(remaining_credit, invoice_remaining))
            if allocation_amount <= _DECIMAL_ZERO:
                continue

            allocation = CreditNoteAllocation(
                credit_note_document_id=credit_note.id,
                invoice_document_id=invoice_id,
                allocated_amount=allocation_amount,
                notes=note_text,
            )
            uow.credit_note_allocations.add(allocation)
            allocations_by_invoice[invoice_id] = _quantize_amount(allocations_by_invoice[invoice_id] + allocation_amount)
            allocations_by_credit_note[credit_note.id] = _quantize_amount(allocations_by_credit_note[credit_note.id] + allocation_amount)
            invoice_balances[invoice_id] = _quantize_amount(invoice_remaining - allocation_amount)
            remaining_credit = _quantize_amount(remaining_credit - allocation_amount)
            total_allocated = _quantize_amount(total_allocated + allocation_amount)

            if remaining_credit <= _DECIMAL_ZERO:
                break

    return allocations_by_invoice, allocations_by_credit_note, total_allocated


def list_open_credit_notes_for_payment_ui() -> List[Document]:
    with UnitOfWork() as uow:
        credit_notes = (
            uow.session.query(Document)
            .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
            .filter(Document.document_type == "credit_note")
            .order_by(Document.document_date.asc(), Document.id.asc())
            .all()
        )

    attach_payment_amounts(credit_notes)
    return [
        credit_note
        for credit_note in credit_notes
        if abs(float(getattr(credit_note, "remaining_amount", 0) or 0)) > 0.004
    ]


def _is_mysql_deadlock_error(exc: OperationalError) -> bool:
    orig = getattr(exc, "orig", None)
    args = getattr(orig, "args", ()) or ()
    if not args:
        return False
    return args[0] == 1213


def _create_placeholder_payment(
    uow: UnitOfWork,
    document: Document,
    *,
    method_code: Optional[str] = None,
) -> Payment:
    expected = Decimal(document.total_gross_amount or 0)
    fallback_due = document.due_date or document.document_date or date.today()
    payment = Payment(
        document_id=document.id,
        due_date=fallback_due,
        expected_amount=expected,
        status="unpaid",
        payment_method=method_code,
    )
    uow.payments.add(payment)
    uow.session.flush()
    return payment


def ensure_document_payment_records(
    uow: UnitOfWork,
    document: Document,
    *,
    method_code: Optional[str] = None,
    mark_paid: bool = False,
    paid_date: Optional[date] = None,
) -> List[Payment]:
    """
    Assicura almeno una scadenza/pagamento per il documento.
    Utile per documenti manuali o flussi che partono senza DatiPagamento.
    """
    payments = uow.payments.get_by_document_id(document.id)
    if not payments:
        payments = [_create_placeholder_payment(uow, document, method_code=method_code)]

    if mark_paid:
        effective_date = (
            paid_date
            or document.registration_date
            or document.document_date
            or document.due_date
            or date.today()
        )
        for payment in payments:
            if payment.expected_amount is not None:
                paid_amount = Decimal(payment.expected_amount)
            else:
                paid_amount = Decimal(document.total_gross_amount or 0) if len(payments) == 1 else Decimal("0")
            payment.paid_amount = paid_amount
            payment.paid_date = effective_date
            payment.status = "paid"

    _update_document_paid_status(uow, document)
    return payments


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
        )
        uow.payments.add(payment)
        
        # Flush per assicurare che il pagamento sia visibile per i calcoli successivi
        uow.session.flush()

        # 3. Aggiorna stato pagato del documento
        _update_document_paid_status(uow, document)

        uow.commit()
        
        logger.info(f"Pagamento di {amount} aggiunto al doc {document_id}")
        return payment

def detach_payment(payment_id: int, *, document_id: Optional[int] = None) -> tuple[bool, str]:
    """
    Scollega i dati di pagamento effettivo mantenendo la scadenza del documento.
    """
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            with UnitOfWork() as uow:
                payment = uow.payments.get_by_id(payment_id)
                if not payment:
                    return False, "Pagamento non trovato."
                if document_id is not None and payment.document_id != document_id:
                    return False, "Pagamento non collegato a questo documento."

                has_payment_link = any(
                    [
                        payment.payment_document_id,
                        payment.paid_date,
                        payment.paid_amount not in (None, 0),
                        (payment.status or "").strip().lower() in {"paid", "partial"},
                    ]
                )
                if not has_payment_link:
                    return False, "Nessun pagamento collegato da staccare."

                owning_document_id = payment.document_id
                document = uow.session.get(Document, owning_document_id)
                payment.payment_document = None
                payment.payment_document_id = None
                payment.paid_date = None
                payment.paid_amount = Decimal("0.00")
                payment.notes = None
                payment.status = "unpaid"

                if document:
                    document.is_paid = False
                    _update_document_paid_status(uow, document)

                uow.commit()
                logger.info(
                    "Pagamento %s scollegato dal documento %s",
                    payment_id,
                    owning_document_id,
                )
                return True, "Pagamento scollegato dal documento."
        except OperationalError as exc:
            if not _is_mysql_deadlock_error(exc):
                raise
            logger.warning(
                "Deadlock MySQL durante stacco pagamento %s (tentativo %s/%s)",
                payment_id,
                attempt,
                max_attempts,
            )
            if attempt >= max_attempts:
                return False, "Database temporaneamente occupato. Riprova tra qualche secondo."
            time.sleep(0.15)

    return False, "Impossibile scollegare il pagamento."


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


def update_payment(
    payment_id: int,
    *,
    paid_date: Optional[date] = None,
    paid_amount: Optional[float] = None,
    payment_method: Optional[str] = None,
    notes: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Aggiorna dati principali di un pagamento e ricalcola lo stato del documento.
    """
    cleaned_method = normalize_payment_method_code(payment_method)

    def _parse_amount(value: Optional[float | str]) -> Optional[Decimal]:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    with UnitOfWork() as uow:
        payment = uow.payments.get_by_id(payment_id)
        if not payment:
            return False, "Pagamento non trovato."

        if paid_date:
            payment.paid_date = paid_date
        if paid_amount is not None:
            payment.paid_amount = _parse_amount(paid_amount)
        if cleaned_method:
            payment.payment_method = cleaned_method
        if notes is not None:
            payment.notes = notes.strip() or None

        expected_amount = Decimal(payment.expected_amount or 0)
        paid_value = Decimal(payment.paid_amount or 0)
        if paid_value <= 0:
            payment.status = "unpaid"
        elif expected_amount and paid_value >= expected_amount:
            payment.status = "paid"
        else:
            payment.status = "partial"

        document = uow.session.get(Document, payment.document_id)
        if document:
            _update_document_paid_status(uow, document)

        uow.commit()
        return True, "Pagamento aggiornato."


def list_paid_payments_page(
    *,
    filters: Optional[PaymentHistoryFilters] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[List[Payment], int, int]:
    """
    Restituisce una pagina dei pagamenti eseguiti (stato paid/partial).
    """
    active_filters = filters or PaymentHistoryFilters()
    with UnitOfWork() as uow:
        return uow.payments.search_paid_history_page(
            q=active_filters.q,
            date_from=active_filters.date_from,
            date_to=active_filters.date_to,
            bank_account_iban=active_filters.bank_account_iban,
            payment_method=active_filters.payment_method,
            page=page,
            page_size=page_size,
        )


def attach_payment_amounts(documents: Sequence[Document]) -> None:
    """Aggiunge campi runtime paid_amount, remaining_amount e payment_overview_status."""
    doc_ids = [doc.id for doc in documents if doc and doc.id]
    if not doc_ids:
        return

    with UnitOfWork() as uow:
        payments_by_document, allocated_in_totals, allocated_out_totals = _get_document_payment_totals(uow, doc_ids)

    for doc in documents:
        if not doc:
            continue
        snapshot = _calculate_document_settlement_snapshot(
            document=doc,
            payment_rows=payments_by_document.get(doc.id, []),
            allocated_in=allocated_in_totals.get(doc.id, _DECIMAL_ZERO),
            allocated_out=allocated_out_totals.get(doc.id, _DECIMAL_ZERO),
        )
        _apply_document_runtime_amounts(doc, snapshot)


def get_payment_event_detail(payment_id: int) -> Optional[dict]:
    """
    Recupera un pagamento e, se appartiene a un documento di pagamento,
    restituisce anche tutti i movimenti collegati allo stesso pagamento cumulativo.
    """
    with UnitOfWork() as uow:
        payment = (
            uow.session.query(Payment)
            .options(
                joinedload(Payment.document).joinedload(Document.supplier),
                joinedload(Payment.payment_document),
            )
            .get(payment_id)
        )
        if not payment:
            return None

        if payment.payment_document_id:
            related_payments = (
                uow.session.query(Payment)
                .options(joinedload(Payment.document).joinedload(Document.supplier))
                .filter(Payment.payment_document_id == payment.payment_document_id)
                .order_by(Payment.id.asc())
                .all()
            )
            payment_document = payment.payment_document
        else:
            related_payments = [payment]
            payment_document = None

        total_paid = float(sum(float(p.paid_amount or 0) for p in related_payments))
        documents_count = len({p.document_id for p in related_payments if p.document_id})

        return {
            "payment": payment,
            "payment_document": payment_document,
            "related_payments": related_payments,
            "total_paid": total_paid,
            "documents_count": documents_count,
        }


def attach_payment_document_file(payment_id: int, file) -> PaymentDocument:
    """
    Collega o aggiorna il PDF di pagamento per un singolo pagamento.
    Se il pagamento appartiene a un batch, aggiorna il documento condiviso.
    """
    if file is None or not getattr(file, "filename", ""):
        raise ValueError("File mancante.")

    with UnitOfWork() as uow:
        payment = (
            uow.session.query(Payment)
            .options(
                joinedload(Payment.document),
                joinedload(Payment.payment_document),
            )
            .get(payment_id)
        )
        if not payment:
            raise ValueError("Pagamento non trovato.")

        safe_name = secure_filename(file.filename) or f"payment_{payment_id}_{date.today().isoformat()}.pdf"
        base_path = settings_service.get_payment_files_storage_path()
        relative_path = scan_service.store_payment_document_file(
            file=file,
            base_path=base_path,
            filename=safe_name,
        )

        payment_document = payment.payment_document
        if payment_document is None:
            payment_document = PaymentDocument(
                supplier_id=payment.document.supplier_id if payment.document else None,
                file_name=safe_name,
                file_path=relative_path,
                payment_type=resolve_payment_document_type(payment.payment_method),
                status="reconciled",
                uploaded_at=datetime.utcnow(),
            )
            uow.session.add(payment_document)
            uow.session.flush()
            payment.payment_document = payment_document
        else:
            payment_document.file_name = safe_name
            payment_document.file_path = relative_path
            if payment.payment_method:
                mapped = map_payment_method_to_document_type(payment.payment_method)
                if mapped and (not payment_document.payment_type or payment_document.payment_type == "sconosciuto"):
                    payment_document.payment_type = mapped
            payment_document.status = "reconciled"
            payment_document.uploaded_at = datetime.utcnow()

        uow.commit()
        return payment_document


def _create_batch_payment_legacy(
    file,
    allocations: Sequence[dict],
    method: Optional[str],
    notes: Optional[str],
    bank_account_iban: Optional[str] = None,
    payment_date: Optional[date] = None,
) -> PaymentDocument:
    """Crea un pagamento cumulativo collegato a più scadenze."""
    if not allocations:
        raise ValueError("Nessuna allocazione fornita per il pagamento cumulativo.")

    today = date.today()
    paid_date = payment_date or today
    cleaned_iban = normalize_iban(bank_account_iban)

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
            payment_type=resolve_payment_document_type(method),
            status="reconciled",
            bank_account_iban=cleaned_iban or None,
        )
        uow.session.add(payment_document)
        uow.session.flush()

        if cleaned_iban:
            account = uow.bank_accounts.get_by_iban(cleaned_iban)
            if not account:
                raise ValueError("IBAN non trovato.")

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
            payment.paid_date = paid_date
            payment.paid_amount = new_paid
            payment.payment_method = method
            payment.notes = notes
            payment.payment_document = payment_document

            touched_documents.add(payment.document_id)

        if cleaned_iban:
            doc_entities = {
                doc.legal_entity_id
                for doc in (
                    uow.session.query(Document.id, Document.legal_entity_id)
                    .filter(Document.id.in_(touched_documents))
                    .all()
                )
            }
            if len(doc_entities) > 1:
                raise ValueError("Seleziona documenti della stessa intestazione per usare un IBAN.")
            if doc_entities and account.legal_entity_id not in doc_entities:
                raise ValueError("IBAN non appartenente all'intestazione selezionata.")

        for document_id in touched_documents:
            document = uow.session.query(Document).get(document_id)
            if not document:
                continue

            _update_document_paid_status(uow, document)

        uow.commit()

        return payment_document

def create_batch_payment_from_documents(
    file,
    document_allocations: List[dict],
    method: Optional[str],
    notes: Optional[str],
    bank_account_iban: Optional[str] = None,
    payment_date: Optional[date] = None,
    credit_note_document_ids: Optional[Sequence[int]] = None,
) -> dict:
    """Registra un pagamento cumulativo e, se richiesto, compensa note di credito."""
    if not document_allocations:
        raise ValueError("Nessuna allocazione fornita per il pagamento cumulativo.")

    today = date.today()
    paid_date = payment_date or today
    cleaned_iban = normalize_iban(bank_account_iban)
    selected_credit_note_ids: list[int] = []
    seen_credit_note_ids: set[int] = set()
    for raw_credit_note_id in credit_note_document_ids or []:
        try:
            credit_note_id = int(raw_credit_note_id)
        except (TypeError, ValueError):
            continue
        if credit_note_id in seen_credit_note_ids:
            continue
        seen_credit_note_ids.add(credit_note_id)
        selected_credit_note_ids.append(credit_note_id)

    results = []

    with UnitOfWork() as uow:
        normalized_allocations: list[dict] = []
        doc_ids: list[int] = []
        for alloc in document_allocations:
            doc_id = int(alloc["document_id"])
            amount = _quantize_amount(_to_decimal(alloc["amount"]))
            if amount <= _DECIMAL_ZERO:
                continue
            normalized_allocations.append({"document_id": doc_id, "amount": amount})
            doc_ids.append(doc_id)

        if not normalized_allocations:
            raise ValueError("Inserisci almeno un importo > 0.")

        documents = (
            uow.session.query(Document)
            .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
            .filter(Document.id.in_(doc_ids))
            .with_for_update()
            .all()
        )
        documents_by_id = {document.id: document for document in documents}
        missing_doc_ids = [doc_id for doc_id in doc_ids if doc_id not in documents_by_id]
        if missing_doc_ids:
            raise ValueError(f"Documenti non trovati: {', '.join(str(doc_id) for doc_id in missing_doc_ids)}")

        payments_by_document, allocated_in_totals, allocated_out_totals = _get_document_payment_totals(uow, doc_ids)

        supplier_ids = set()
        legal_entity_ids = set()
        requested_bank_amounts: dict[int, Decimal] = {}
        touched_documents: set[int] = set()

        for alloc in normalized_allocations:
            document = documents_by_id[alloc["document_id"]]
            if _is_credit_note_document(document):
                raise ValueError("Le note di credito vanno selezionate dal box dedicato, non dalla lista fatture.")

            supplier_ids.add(document.supplier_id)
            legal_entity_ids.add(document.legal_entity_id)
            snapshot = _calculate_document_settlement_snapshot(
                document=document,
                payment_rows=payments_by_document.get(document.id, []),
                allocated_in=allocated_in_totals.get(document.id, _DECIMAL_ZERO),
                allocated_out=allocated_out_totals.get(document.id, _DECIMAL_ZERO),
            )
            current_remaining = _quantize_amount(snapshot["remaining_amount"])
            requested_amount = alloc["amount"]
            if current_remaining <= _DECIMAL_ZERO:
                raise ValueError(f"Il documento {document.document_number or document.id} non ha piu residuo da saldare.")
            if requested_amount > current_remaining:
                raise ValueError(
                    f"L'importo richiesto per il documento {document.document_number or document.id} supera il residuo disponibile."
                )
            requested_bank_amounts[document.id] = requested_amount

        if cleaned_iban:
            account = uow.bank_accounts.get_by_iban(cleaned_iban)
            if not account:
                raise ValueError("IBAN non trovato.")
            if len(legal_entity_ids) > 1:
                raise ValueError("Seleziona documenti della stessa intestazione per usare un IBAN.")
            if legal_entity_ids and account.legal_entity_id not in legal_entity_ids:
                raise ValueError("IBAN non appartenente all'intestazione selezionata.")
        else:
            account = None

        selected_credit_notes: list[Document] = []
        credit_allocations_by_invoice: dict[int, Decimal] = {document_id: _DECIMAL_ZERO for document_id in requested_bank_amounts}
        credit_applied_total = _DECIMAL_ZERO

        if selected_credit_note_ids:
            if _has_recent_duplicate_credit_allocation(
                uow,
                invoice_document_ids=list(requested_bank_amounts.keys()),
                credit_note_document_ids=selected_credit_note_ids,
            ):
                raise DuplicatePaymentSubmissionError(
                    "Compensazione gia registrata pochi secondi fa. Aggiorna la pagina per vedere lo stato aggiornato."
                )

            if len(supplier_ids) != 1 or len(legal_entity_ids) != 1:
                raise ValueError("Per compensare note di credito seleziona fatture dello stesso fornitore e della stessa intestazione.")

            credit_notes = (
                uow.session.query(Document)
                .options(joinedload(Document.supplier), joinedload(Document.legal_entity))
                .filter(Document.id.in_(selected_credit_note_ids))
                .all()
            )
            credit_notes_by_id = {document.id: document for document in credit_notes}
            missing_credit_note_ids = [doc_id for doc_id in selected_credit_note_ids if doc_id not in credit_notes_by_id]
            if missing_credit_note_ids:
                raise ValueError(
                    f"Note di credito non trovate: {', '.join(str(doc_id) for doc_id in missing_credit_note_ids)}"
                )

            selected_supplier_id = next(iter(supplier_ids))
            selected_legal_entity_id = next(iter(legal_entity_ids))
            for credit_note_id in selected_credit_note_ids:
                credit_note = credit_notes_by_id[credit_note_id]
                if not _is_credit_note_document(credit_note):
                    raise ValueError("Sono selezionabili solo documenti di tipo nota di credito.")
                if credit_note.supplier_id != selected_supplier_id:
                    raise ValueError("Le note di credito selezionate devono appartenere allo stesso fornitore delle fatture.")
                if credit_note.legal_entity_id != selected_legal_entity_id:
                    raise ValueError("Le note di credito selezionate devono appartenere alla stessa intestazione delle fatture.")
                selected_credit_notes.append(credit_note)

            bank_balances = {document_id: amount for document_id, amount in requested_bank_amounts.items()}
            credit_allocations_by_invoice, _, credit_applied_total = _allocate_credit_note_amounts(
                uow=uow,
                credit_notes=selected_credit_notes,
                invoice_balances=bank_balances,
                notes=notes,
            )
            requested_bank_amounts = bank_balances

        bank_payment_total = _quantize_amount(sum(requested_bank_amounts.values(), _DECIMAL_ZERO))

        if _has_recent_duplicate_payment_submission(
            uow,
            document_amounts=requested_bank_amounts,
            paid_date=paid_date,
            method=method,
            bank_account_iban=cleaned_iban or None,
        ):
            raise DuplicatePaymentSubmissionError(
                "Richiesta gia registrata pochi secondi fa. Aggiorna la pagina per vedere lo stato aggiornato."
            )

        payment_document = None
        if bank_payment_total > _DECIMAL_ZERO:
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
                    payment_type=resolve_payment_document_type(method),
                    status="reconciled",
                    bank_account_iban=cleaned_iban or None,
                    uploaded_at=datetime.utcnow(),
                )
            else:
                placeholder_name = f"batch_payment_{today.isoformat()}"
                payment_document = PaymentDocument(
                    file_name=placeholder_name,
                    file_path=placeholder_name,
                    payment_type=resolve_payment_document_type(method),
                    status="reconciled",
                    bank_account_iban=cleaned_iban or None,
                    uploaded_at=datetime.utcnow(),
                )
            payment_document.supplier_id = next(iter(supplier_ids), None)
            uow.session.add(payment_document)
            uow.session.flush()
        elif file and file.filename:
            logger.info("Allegato pagamento ignorato: saldo interamente compensato da note di credito.")

        unpaid_payments = uow.payments.get_unpaid_by_document_ids(doc_ids)
        payment_map: dict[int, list[Payment]] = {}
        for payment in unpaid_payments:
            payment_map.setdefault(payment.document_id, []).append(payment)

        for alloc in normalized_allocations:
            doc_id = alloc["document_id"]
            document = documents_by_id[doc_id]
            bank_amount = _quantize_amount(requested_bank_amounts.get(doc_id, _DECIMAL_ZERO))

            try:
                payment = None
                if bank_amount > _DECIMAL_ZERO:
                    if doc_id not in payment_map or not payment_map[doc_id]:
                        payment = _create_placeholder_payment(uow, document, method_code=method)
                        payment_map.setdefault(doc_id, []).append(payment)
                    else:
                        payment = payment_map[doc_id][0]

                    current_paid = _to_decimal(payment.paid_amount)
                    new_paid = _quantize_amount(current_paid + bank_amount)
                    payment.paid_date = paid_date
                    payment.paid_amount = new_paid
                    payment.payment_method = method
                    payment.notes = notes
                    payment.payment_document = payment_document

                    expected_amount = _quantize_amount(_to_decimal(payment.expected_amount))
                    if expected_amount > _DECIMAL_ZERO and new_paid >= expected_amount:
                        payment.status = "paid"
                    else:
                        payment.status = "partial"

                touched_documents.add(doc_id)
                results.append({
                    "document_id": doc_id,
                    "success": True,
                    "payment_id": payment.id if payment else None,
                    "credit_note_allocated_amount": float(credit_allocations_by_invoice.get(doc_id, _DECIMAL_ZERO)),
                    "bank_paid_amount": float(bank_amount),
                })
            except Exception as exc:
                logger.exception("Failed to process payment for doc %s", doc_id)
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(exc),
                })

        touched_documents.update(selected_credit_note_ids)

        for document_id in touched_documents:
            document = uow.session.get(Document, document_id)
            if document:
                _update_document_paid_status(uow, document)

        uow.commit()

    success_count = len([result for result in results if result["success"]])
    error_count = len([result for result in results if not result["success"]])

    logger.info(
        "Pagamento multiplo registrato: documenti=%s compensato=%s netto=%s note_credito=%s",
        success_count,
        credit_applied_total,
        bank_payment_total,
        len(selected_credit_note_ids),
    )

    return {
        "success_count": success_count,
        "error_count": error_count,
        "results": results,
        "credit_note_applied_total": float(credit_applied_total),
        "bank_payment_total": float(bank_payment_total),
        "credit_note_count": len(selected_credit_note_ids),
    }


def register_instant_payment_for_document(
    document_id: int,
    *,
    bank_account_iban: Optional[str] = None,
    paid_date: Optional[date] = None,
) -> tuple[bool, str]:
    """
    Registra un pagamento istantaneo senza documento PDF.
    """
    cleaned_iban = normalize_iban(bank_account_iban)

    with UnitOfWork() as uow:
        document = uow.session.get(Document, document_id)
        if not document:
            return False, "Documento non trovato."

        if cleaned_iban:
            account = uow.bank_accounts.get_by_iban(cleaned_iban)
            if not account:
                return False, "IBAN non trovato."
            if document.legal_entity_id and account.legal_entity_id != document.legal_entity_id:
                return False, "IBAN non appartenente all'intestazione selezionata."

        payments = uow.payments.get_by_document_id(document_id)
        if not payments:
            if paid_date and document.due_date is None:
                document.due_date = paid_date
            payment = _create_placeholder_payment(uow, document)
            payments = [payment]

        effective_date = paid_date or document.document_date or document.due_date or date.today()
        method_code = payments[0].payment_method if payments else None
        payment_type = resolve_payment_document_type(method_code)

        payment_document = None
        for payment in payments:
            if payment.payment_document:
                payment_document = payment.payment_document
                break

        if payment_document is None:
            placeholder_name = f"instant_payment_{document_id}_{effective_date.isoformat()}"
            payment_document = PaymentDocument(
                supplier_id=document.supplier_id,
                file_name=placeholder_name,
                file_path=placeholder_name,
                payment_type=payment_type,
                status="reconciled",
                bank_account_iban=cleaned_iban or None,
                uploaded_at=datetime.utcnow(),
            )
            uow.session.add(payment_document)
            uow.session.flush()
        else:
            if not payment_document.payment_type or payment_document.payment_type == "sconosciuto":
                payment_document.payment_type = payment_type
            if cleaned_iban:
                payment_document.bank_account_iban = cleaned_iban
            payment_document.status = "reconciled"
            payment_document.uploaded_at = datetime.utcnow()

        for payment in payments:
            if payment.expected_amount is not None:
                paid_amount = Decimal(payment.expected_amount)
            else:
                paid_amount = Decimal(document.total_gross_amount or 0) if len(payments) == 1 else Decimal("0")
            payment.paid_amount = paid_amount
            payment.paid_date = effective_date
            payment.status = "paid"
            payment.payment_document = payment_document

        _update_document_paid_status(uow, document)
        uow.commit()

    return True, "Pagamento istantaneo registrato."

def update_payment_method_for_document(
    document_id: int,
    method_code: Optional[str],
) -> tuple[bool, str]:
    """
    Aggiorna il metodo di pagamento per tutte le scadenze del documento.
    """
    normalized = normalize_payment_method_code(method_code)
    if not normalized or not is_known_payment_method(normalized):
        return False, "Metodo di pagamento non valido."

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        try:
            with UnitOfWork() as uow:
                document = uow.session.get(Document, document_id)
                if not document:
                    return False, "Documento non trovato."

                payments = uow.payments.get_by_document_id(document_id)
                if not payments:
                    payment = _create_placeholder_payment(uow, document, method_code=normalized)
                    payments = [payment]

                for payment in payments:
                    payment.payment_method = normalized

                if is_physical_copy_required(normalized):
                    if document.physical_copy_status == "not_required":
                        document.physical_copy_status = "missing"
                else:
                    if document.physical_copy_status in {"missing", "requested"}:
                        document.physical_copy_status = "not_required"

                uow.commit()
                return True, "Metodo di pagamento aggiornato."
        except OperationalError as exc:
            if not _is_mysql_deadlock_error(exc):
                raise
            logger.warning(
                "Deadlock MySQL durante aggiornamento metodo pagamento doc %s (tentativo %s/%s)",
                document_id,
                attempt,
                max_attempts,
            )
            if attempt >= max_attempts:
                return False, "Database temporaneamente occupato. Riprova tra qualche secondo."
            time.sleep(0.15)

def _update_document_paid_status(uow: UnitOfWork, document: Document):
    """Helper interno: ricalcola se il documento e` completamente regolato."""
    if not document or not document.id:
        return

    payments_by_document, allocated_in_totals, allocated_out_totals = _get_document_payment_totals(uow, [document.id])
    snapshot = _calculate_document_settlement_snapshot(
        document=document,
        payment_rows=payments_by_document.get(document.id, []),
        allocated_in=allocated_in_totals.get(document.id, _DECIMAL_ZERO),
        allocated_out=allocated_out_totals.get(document.id, _DECIMAL_ZERO),
    )

    if _is_credit_note_document(document):
        document.is_paid = snapshot["available_credit_amount"] <= _DECIMAL_ZERO
    else:
        gross_amount = snapshot["gross_amount"]
        if gross_amount <= _DECIMAL_ZERO:
            document.is_paid = True
        else:
            document.is_paid = snapshot["remaining_amount"] <= _DECIMAL_ZERO


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
