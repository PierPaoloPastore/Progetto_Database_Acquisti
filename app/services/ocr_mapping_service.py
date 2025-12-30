"""
Parsing OCR per precompilare i campi dei form.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.models import Supplier
from app.services.unit_of_work import UnitOfWork


AMOUNT_REGEX = r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})|\d+[.,]\d{2}|\d+)"
DATE_REGEX = r"(\d{1,2})[\/\.\-](\d{1,2})[\/\.\-](\d{2,4})"


def parse_payment_fields(text: str) -> dict:
    normalized = _normalize_text(text)
    lowered = normalized.lower()
    fields: dict[str, dict] = {}

    amount = _find_amount_by_keywords(normalized, ["totale", "importo", "tot.", "tot"])
    if amount is None:
        amount = _find_largest_amount(normalized)
        confidence = 0.55
    else:
        confidence = 0.8
    if amount is not None:
        fields["amount"] = _field(amount, confidence)

    method = _find_payment_method(lowered)
    if method:
        fields["payment_method"] = _field(method, 0.7)

    pay_date = _find_date_by_keywords(normalized, ["data pagamento", "pagamento", "data"])
    if pay_date:
        fields["payment_date"] = _field(pay_date, 0.6)

    if normalized:
        snippet = normalized[:300].strip()
        fields["notes"] = _field(snippet, 0.4)

    return fields


def parse_ddt_fields(text: str) -> dict:
    normalized = _normalize_text(text)
    lowered = normalized.lower()
    fields: dict[str, dict] = {}

    ddt_number = _find_ddt_number(normalized)
    if ddt_number:
        fields["ddt_number"] = _field(ddt_number, 0.8)

    ddt_date = _find_date_by_keywords(normalized, ["data ddt", "ddt", "data"])
    if ddt_date:
        fields["ddt_date"] = _field(ddt_date, 0.75)

    total = _find_amount_by_keywords(normalized, ["totale", "importo", "tot."])
    if total is not None:
        fields["total_amount"] = _field(total, 0.75)

    supplier_match = _match_supplier(lowered)
    if supplier_match:
        supplier_id, supplier_name, confidence = supplier_match
        fields["supplier_id"] = _field(str(supplier_id), confidence)
        fields["supplier_name"] = _field(supplier_name, confidence)

    if normalized:
        fields["notes"] = _field(normalized[:300].strip(), 0.4)

    return fields


def parse_manual_document_fields(text: str) -> dict:
    normalized = _normalize_text(text)
    lowered = normalized.lower()
    fields: dict[str, dict] = {}

    doc_number = _find_document_number(normalized)
    if doc_number:
        fields["document_number"] = _field(doc_number, 0.7)

    doc_date = _find_date_by_keywords(normalized, ["data documento", "data doc", "data"])
    if doc_date:
        fields["document_date"] = _field(doc_date, 0.7)

    due_date = _find_date_by_keywords(normalized, ["scadenza", "pagare entro", "data scadenza"])
    if due_date:
        fields["due_date"] = _field(due_date, 0.6)

    imponibile = _find_amount_by_keywords(normalized, ["imponibile", "netto"])
    if imponibile is not None:
        fields["total_taxable_amount"] = _field(imponibile, 0.75)

    iva = _find_amount_by_keywords(normalized, ["iva", "imposta"])
    if iva is not None:
        fields["total_vat_amount"] = _field(iva, 0.75)

    totale = _find_amount_by_keywords(normalized, ["totale", "importo", "tot."])
    if totale is not None:
        fields["total_gross_amount"] = _field(totale, 0.75)

    doc_type = _detect_manual_doc_type(lowered)
    if doc_type:
        fields["document_type"] = _field(doc_type, 0.65)

    supplier_match = _match_supplier(lowered)
    if supplier_match:
        supplier_id, supplier_name, confidence = supplier_match
        fields["supplier_id"] = _field(str(supplier_id), confidence)
        fields["supplier_name"] = _field(supplier_name, confidence)

    if normalized:
        fields["note"] = _field(normalized[:300].strip(), 0.4)

    return fields


def _normalize_text(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split())


def _field(value: str, confidence: float) -> dict:
    return {"value": value, "confidence": round(confidence, 2)}


def _parse_amount(raw: str) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.replace(" ", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return f"{value:.2f}"


def _find_amount_by_keywords(text: str, keywords: list[str]) -> Optional[str]:
    for keyword in keywords:
        pattern = re.compile(rf"{re.escape(keyword)}\s*[:\-]?\s*{AMOUNT_REGEX}", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            amount_raw = match.group(1)
            parsed = _parse_amount(amount_raw)
            if parsed is not None:
                return parsed
    return None


def _find_largest_amount(text: str) -> Optional[str]:
    matches = re.findall(AMOUNT_REGEX, text)
    if not matches:
        return None
    values: list[Decimal] = []
    for raw in matches:
        parsed = _parse_amount(raw)
        if parsed is None:
            continue
        try:
            values.append(Decimal(parsed))
        except InvalidOperation:
            continue
    if not values:
        return None
    return f"{max(values):.2f}"


def _find_date_by_keywords(text: str, keywords: list[str]) -> Optional[str]:
    for keyword in keywords:
        pattern = re.compile(rf"{re.escape(keyword)}[^\d]{{0,12}}{DATE_REGEX}", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return _format_date(match.group(1), match.group(2), match.group(3))
    generic = re.search(DATE_REGEX, text)
    if generic:
        return _format_date(generic.group(1), generic.group(2), generic.group(3))
    return None


def _format_date(day: str, month: str, year: str) -> Optional[str]:
    try:
        day_int = int(day)
        month_int = int(month)
        year_int = int(year)
        if year_int < 100:
            year_int += 2000
        value = date(year_int, month_int, day_int)
        return value.isoformat()
    except Exception:
        return None


def _find_payment_method(text: str) -> Optional[str]:
    mapping = {
        "bonifico": ["bonifico", "sepa"],
        "assegno": ["assegno"],
        "contanti": ["contanti", "cash"],
        "altro": ["carta", "pos", "paypal"],
    }
    for method, keys in mapping.items():
        for key in keys:
            if key in text:
                return method
    return None


def _find_ddt_number(text: str) -> Optional[str]:
    match = re.search(r"\bddt\b[^\w]{0,6}([a-z0-9\/\.\-]{3,})", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def _find_document_number(text: str) -> Optional[str]:
    match = re.search(r"\b(?:numero|num\.?|n\.)\s*[:\-]?\s*([a-z0-9\/\.\-]{3,})", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def _detect_manual_doc_type(text: str) -> Optional[str]:
    if "f24" in text:
        return "f24"
    if "cbill" in text:
        return "cbill"
    if "mav" in text:
        return "mav"
    if "assicur" in text:
        return "insurance"
    if "affitto" in text or "locazione" in text:
        return "rent"
    if "scontrino" in text or "ricevuta" in text:
        return "receipt"
    if "tributo" in text or "tassa" in text:
        return "tax"
    return None


def _match_supplier(text: str) -> Optional[tuple[int, str, float]]:
    if not text:
        return None
    normalized = text.lower()
    with UnitOfWork() as uow:
        suppliers = uow.session.query(Supplier).all()

    best = None
    best_len = 0
    for supplier in suppliers:
        name = (supplier.name or "").strip()
        if not name:
            continue
        name_lower = name.lower()
        if name_lower in normalized and len(name_lower) >= 4:
            score = min(0.9, 0.6 + len(name_lower) / 40)
            if len(name_lower) > best_len:
                best = (supplier.id, name, score)
                best_len = len(name_lower)
    return best
