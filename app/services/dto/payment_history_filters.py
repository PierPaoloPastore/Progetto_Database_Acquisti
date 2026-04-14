"""DTO e helper per i filtri della cronologia pagamenti."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping, Optional

from app.services.bank_account_service import normalize_iban
from app.services.payment_method_catalog import normalize_payment_method_code


@dataclass
class PaymentHistoryFilters:
    q: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    bank_account_iban: Optional[str] = None
    payment_method: Optional[str] = None

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    @classmethod
    def from_query_args(cls, args: Mapping[str, Any]) -> "PaymentHistoryFilters":
        q_raw = (args.get("q") or "").strip()
        date_from = cls._parse_date(args.get("date_from", ""))
        date_to = cls._parse_date(args.get("date_to", ""))
        if date_from and date_to and date_from > date_to:
            date_from, date_to = date_to, date_from

        bank_account_iban = normalize_iban(args.get("bank_account_iban") or "") or None
        payment_method = normalize_payment_method_code(args.get("payment_method") or "")

        return cls(
            q=q_raw or None,
            date_from=date_from,
            date_to=date_to,
            bank_account_iban=bank_account_iban,
            payment_method=payment_method or None,
        )

    @property
    def has_advanced_filters(self) -> bool:
        return any(
            (
                self.date_from,
                self.date_to,
                self.bank_account_iban,
                self.payment_method,
            )
        )

    @property
    def has_filters(self) -> bool:
        return bool(self.q) or self.has_advanced_filters
