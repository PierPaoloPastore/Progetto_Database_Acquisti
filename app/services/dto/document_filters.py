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
    supplier_id: Optional[int] = None
    legal_entity_id: Optional[int] = None
    year: Optional[int] = None
    doc_status: Optional[str] = None
    physical_copy_status: Optional[str] = None
    payment_status: Optional[str] = None
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
        return cls(
            date_from=cls._parse_date(args.get("date_from", "")),
            date_to=cls._parse_date(args.get("date_to", "")),
            supplier_id=cls._parse_int(args.get("supplier_id")),
            legal_entity_id=cls._parse_int(args.get("legal_entity_id")),
            year=cls._parse_int(args.get("year")),
            doc_status=(args.get("doc_status") or None),
            physical_copy_status=(args.get("physical_copy_status") or None),
            payment_status=(args.get("payment_status") or None),
            min_total=cls._parse_decimal(args.get("min_total", "")),
            max_total=cls._parse_decimal(args.get("max_total", "")),
        )
