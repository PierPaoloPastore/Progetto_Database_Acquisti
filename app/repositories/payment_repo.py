"""Repository specifico per Payment."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

from app.models import Document, LegalEntity, Payment, PaymentDocument, Supplier
from app.repositories.base import SqlAlchemyRepository
from app.services.payment_method_catalog import (
    PAYMENT_METHOD_LABELS,
    map_payment_method_to_document_type,
    normalize_payment_method_code,
)


def _normalize_iban(raw: str | None) -> str:
    if not raw:
        return ""
    return "".join(str(raw).split()).upper()


class PaymentRepository(SqlAlchemyRepository[Payment]):
    def __init__(self, session):
        super().__init__(session, Payment)

    def get_by_document_id(self, document_id: int) -> List[Payment]:
        """Restituisce tutti i pagamenti associati a un documento."""
        return (
            self.session.query(Payment)
            .filter_by(document_id=document_id)
            .order_by(Payment.due_date.asc())
            .all()
        )

    def get_unpaid_by_document_ids(self, document_ids: List[int]) -> List[Payment]:
        """Restituisce i pagamenti unpaid/partial per i documenti richiesti."""
        return (
            self.session.query(Payment)
            .filter(
                Payment.document_id.in_(document_ids),
                Payment.status.in_(["unpaid", "partial"]),
            )
            .order_by(Payment.document_id.asc(), Payment.due_date.asc())
            .all()
        )

    @staticmethod
    def _parse_search_date(value: str) -> Optional[date]:
        for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, pattern).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_search_decimal(value: str) -> Optional[Decimal]:
        cleaned = (value or "").strip().replace(" ", "")
        if not cleaned:
            return None
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", ".")
        try:
            return Decimal(cleaned)
        except (InvalidOperation, ValueError):
            return None

    def _apply_history_search(self, query, search_text: str):
        like_value = f"%{search_text}%"
        normalized_code = normalize_payment_method_code(search_text)
        normalized_iban = _normalize_iban(search_text)
        lowered = search_text.lower()
        parsed_id = int(search_text) if search_text.isdigit() else None
        parsed_date = self._parse_search_date(search_text)
        parsed_amount = self._parse_search_decimal(search_text)
        matching_method_codes = [
            code
            for code, label in PAYMENT_METHOD_LABELS.items()
            if lowered in code.lower() or lowered in label.lower()
        ]

        search_filters = [
            Document.document_number.ilike(like_value),
            Supplier.name.ilike(like_value),
            LegalEntity.name.ilike(like_value),
            Payment.notes.ilike(like_value),
            Payment.status.ilike(like_value),
            Payment.payment_method.ilike(like_value),
            PaymentDocument.file_name.ilike(like_value),
            PaymentDocument.payment_type.ilike(like_value),
        ]

        if normalized_iban and len(normalized_iban) >= 4:
            search_filters.append(PaymentDocument.bank_account_iban.ilike(f"%{normalized_iban}%"))

        if parsed_id is not None:
            search_filters.extend(
                [
                    Payment.id == parsed_id,
                    Document.id == parsed_id,
                    Payment.payment_document_id == parsed_id,
                ]
            )

        if parsed_date is not None:
            search_filters.append(Payment.paid_date == parsed_date)

        if parsed_amount is not None:
            search_filters.extend(
                [
                    Payment.paid_amount == parsed_amount,
                    and_(
                        Payment.paid_amount.is_(None),
                        Payment.expected_amount == parsed_amount,
                    ),
                ]
            )

        if normalized_code:
            search_filters.append(Payment.payment_method == normalized_code)
        if matching_method_codes:
            search_filters.append(Payment.payment_method.in_(matching_method_codes))

        return query.filter(or_(*search_filters))

    def search_paid_history_page(
        self,
        *,
        q: str | None = None,
        date_from=None,
        date_to=None,
        bank_account_iban: str | None = None,
        payment_method: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[Payment], int, int]:
        """Restituisce una pagina della cronologia pagamenti con filtri avanzati."""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50

        query = (
            self.session.query(Payment)
            .join(Document, Payment.document_id == Document.id)
            .outerjoin(Supplier, Document.supplier_id == Supplier.id)
            .outerjoin(LegalEntity, Document.legal_entity_id == LegalEntity.id)
            .outerjoin(PaymentDocument, Payment.payment_document_id == PaymentDocument.id)
            .options(
                joinedload(Payment.document).joinedload(Document.supplier),
                joinedload(Payment.document).joinedload(Document.legal_entity),
                joinedload(Payment.payment_document),
            )
            .filter(Payment.status.in_(["paid", "partial"]))
        )

        if date_from is not None:
            query = query.filter(Payment.paid_date >= date_from)
        if date_to is not None:
            query = query.filter(Payment.paid_date <= date_to)
        if bank_account_iban:
            query = query.filter(PaymentDocument.bank_account_iban == bank_account_iban)
        if payment_method:
            payment_type = map_payment_method_to_document_type(payment_method)
            if payment_type:
                query = query.filter(
                    or_(
                        Payment.payment_method == payment_method,
                        PaymentDocument.payment_type == payment_type,
                    )
                )
            else:
                query = query.filter(Payment.payment_method == payment_method)

        search_text = (q or "").strip()
        if search_text:
            query = self._apply_history_search(query, search_text)

        total = query.order_by(None).count()
        if total:
            max_page = (total - 1) // page_size + 1
            page = min(page, max_page)
        else:
            page = 1

        items = (
            query.order_by(Payment.paid_date.desc(), Payment.updated_at.desc(), Payment.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total, page
