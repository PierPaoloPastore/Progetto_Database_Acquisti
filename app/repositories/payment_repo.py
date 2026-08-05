"""Repository specifico per Payment."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from sqlalchemy import and_, case, func, or_
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

    def list_recent_paid_by_documents(
        self,
        document_ids: List[int],
        *,
        paid_date: date,
        since: datetime,
    ) -> List[Payment]:
        """Restituisce pagamenti recenti usati per bloccare submit duplicati."""
        if not document_ids:
            return []
        return (
            self.session.query(Payment)
            .outerjoin(PaymentDocument, Payment.payment_document_id == PaymentDocument.id)
            .options(joinedload(Payment.payment_document))
            .filter(
                Payment.document_id.in_(document_ids),
                Payment.status.in_(["paid", "partial"]),
                Payment.paid_date == paid_date,
                Payment.updated_at >= since,
            )
            .order_by(Payment.updated_at.desc(), Payment.id.desc())
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

    def _build_paid_history_query(
        self,
        *,
        q: str | None = None,
        date_from=None,
        date_to=None,
        bank_account_iban: str | None = None,
        payment_method: str | None = None,
        include_options: bool = True,
    ):
        query = (
            self.session.query(Payment)
            .join(Document, Payment.document_id == Document.id)
            .outerjoin(Supplier, Document.supplier_id == Supplier.id)
            .outerjoin(LegalEntity, Document.legal_entity_id == LegalEntity.id)
            .outerjoin(PaymentDocument, Payment.payment_document_id == PaymentDocument.id)
            .filter(Payment.status.in_(["paid", "partial"]))
        )
        if include_options:
            query = query.options(
                joinedload(Payment.document).joinedload(Document.supplier),
                joinedload(Payment.document).joinedload(Document.legal_entity),
                joinedload(Payment.payment_document),
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

        return query

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

        query = self._build_paid_history_query(
            q=q,
            date_from=date_from,
            date_to=date_to,
            bank_account_iban=bank_account_iban,
            payment_method=payment_method,
            include_options=True,
        )

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

    def search_paid_history_events_page(
        self,
        *,
        q: str | None = None,
        date_from=None,
        date_to=None,
        bank_account_iban: str | None = None,
        payment_method: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[List[List[Payment]], int, int]:
        """Restituisce una pagina di eventi: batch aggregati e pagamenti singoli."""
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 50

        query = self._build_paid_history_query(
            q=q,
            date_from=date_from,
            date_to=date_to,
            bank_account_iban=bank_account_iban,
            payment_method=payment_method,
            include_options=False,
        )

        group_payment_document_id = Payment.payment_document_id.label("payment_document_id")
        group_single_payment_id = case(
            (Payment.payment_document_id.is_(None), Payment.id),
            else_=None,
        ).label("single_payment_id")
        event_paid_date = func.max(Payment.paid_date).label("event_paid_date")
        event_updated_at = func.max(Payment.updated_at).label("event_updated_at")
        event_payment_id = func.max(Payment.id).label("event_payment_id")

        grouped_query = (
            query.with_entities(
                group_payment_document_id,
                group_single_payment_id,
                event_paid_date,
                event_updated_at,
                event_payment_id,
            )
            .group_by(group_payment_document_id, group_single_payment_id)
        )

        total = grouped_query.order_by(None).count()
        if total:
            max_page = (total - 1) // page_size + 1
            page = min(page, max_page)
        else:
            page = 1

        event_rows = (
            grouped_query.order_by(
                event_paid_date.desc(),
                event_updated_at.desc(),
                event_payment_id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        payment_document_ids = [
            row.payment_document_id for row in event_rows if row.payment_document_id is not None
        ]
        single_payment_ids = [
            row.single_payment_id for row in event_rows if row.single_payment_id is not None
        ]
        if not payment_document_ids and not single_payment_ids:
            return [], total, page

        related_query = (
            self.session.query(Payment)
            .options(
                joinedload(Payment.document).joinedload(Document.supplier),
                joinedload(Payment.document).joinedload(Document.legal_entity),
                joinedload(Payment.payment_document),
            )
            .filter(Payment.status.in_(["paid", "partial"]))
        )
        related_filters = []
        if payment_document_ids:
            related_filters.append(Payment.payment_document_id.in_(payment_document_ids))
        if single_payment_ids:
            related_filters.append(Payment.id.in_(single_payment_ids))
        related_payments = (
            related_query.filter(or_(*related_filters))
            .order_by(Payment.paid_date.desc(), Payment.updated_at.desc(), Payment.id.desc())
            .all()
        )

        by_document_id: dict[int, list[Payment]] = {}
        by_single_id: dict[int, list[Payment]] = {}
        for payment in related_payments:
            if payment.payment_document_id:
                by_document_id.setdefault(payment.payment_document_id, []).append(payment)
            else:
                by_single_id[payment.id] = [payment]

        events = []
        for row in event_rows:
            if row.payment_document_id is not None:
                payments = by_document_id.get(row.payment_document_id, [])
            else:
                payments = by_single_id.get(row.single_payment_id, [])
            if payments:
                events.append(payments)

        return events, total, page
