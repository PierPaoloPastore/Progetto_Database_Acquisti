"""
Helper per la formattazione numerica centralizzata.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from flask import current_app

from app.services.settings_service import get_setting

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in _TRUE_VALUES


def use_thousands_separator() -> bool:
    cached = current_app.config.get("FORMAT_THOUSANDS_SEPARATOR")
    if cached is None:
        cached = get_setting("FORMAT_THOUSANDS_SEPARATOR", "0")
        current_app.config["FORMAT_THOUSANDS_SEPARATOR"] = cached
    return _parse_bool(cached)


def format_number(value: Any, decimals: int = 2, use_grouping: Optional[bool] = None) -> str:
    if value in (None, ""):
        return ""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    if decimals < 0:
        decimals = 0
    if use_grouping is None:
        use_grouping = use_thousands_separator()

    quant = Decimal("1") if decimals == 0 else Decimal("1").scaleb(-decimals)
    try:
        number = number.quantize(quant)
    except InvalidOperation:
        pass

    format_spec = f",.{decimals}f" if use_grouping else f".{decimals}f"
    return format(number, format_spec)


def format_amount(value: Any, use_grouping: Optional[bool] = None) -> str:
    return format_number(value, decimals=2, use_grouping=use_grouping)


def format_int(value: Any, use_grouping: Optional[bool] = None) -> str:
    return format_number(value, decimals=0, use_grouping=use_grouping)
