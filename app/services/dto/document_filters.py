"""DTO e helper per i filtri di ricerca documenti."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Optional


@dataclass
class DocumentSearchFilters:
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    document_number: Optional[str] = None
    supplier_id: Optional[int] = None
    legal_entity_id: Optional[int] = None
    accounting_year: Optional[int] = None  # <--- RINOMINATO (era 'year')
    doc_status: Optional[str] = None
    physical_copy_status: Optional[str] = None
    payment_status: Optional[str] = None
    amount_operator: str = "gt"
    amount_value: Optional[Decimal] = None
    min_total: Optional[Decimal] = None
    max_total: Optional[Decimal] = None

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_decimal(value: Any) -> Optional[Decimal]:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value).replace(",", "."))
        except (InvalidOperation, AttributeError):
            return None

    @classmethod
    def from_query_args(cls, args: Mapping[str, Any]) -> "DocumentSearchFilters":
        document_number_raw = (args.get("document_number") or "").strip()
        amount_value = cls._parse_decimal(args.get("amount_value", ""))
        amount_operator = (args.get("amount_operator") or "").strip().lower()
        if amount_operator not in {"lt", "gt"}:
            amount_operator = "gt"
        min_total = cls._parse_decimal(args.get("min_total", ""))
        max_total = cls._parse_decimal(args.get("max_total", ""))
        if amount_value is not None:
            if amount_operator == "lt":
                max_total = amount_value
                min_total = None
            else:
                min_total = amount_value
                max_total = None
        else:
            if min_total is not None and max_total is None:
                amount_value = min_total
                amount_operator = "gt"
            elif max_total is not None and min_total is None:
                amount_value = max_total
                amount_operator = "lt"
        return cls(
            date_from=cls._parse_date(args.get("date_from", "")),
            date_to=cls._parse_date(args.get("date_to", "")),
            document_number=document_number_raw or None,
            supplier_id=cls._parse_int(args.get("supplier_id")),
            legal_entity_id=cls._parse_int(args.get("legal_entity_id")),
            accounting_year=cls._parse_int(args.get("accounting_year") or args.get("year")), # Mappiamo il parametro URL 'year' sull'attributo 'accounting_year'
            doc_status=(args.get("doc_status") or None),
            physical_copy_status=(args.get("physical_copy_status") or None),
            payment_status=(args.get("payment_status") or None),
            amount_operator=amount_operator,
            amount_value=amount_value,
            min_total=min_total,
            max_total=max_total,
        )
