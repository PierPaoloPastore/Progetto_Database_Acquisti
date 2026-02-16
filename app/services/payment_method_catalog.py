"""
Catalogo metodi di pagamento FatturaPA (MP01-MP22).
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple


PAYMENT_METHOD_LABELS: Dict[str, str] = {
    "MP01": "Contanti",
    "MP02": "Assegno",
    "MP03": "Assegno circolare",
    "MP04": "Contanti presso Tesoreria",
    "MP05": "Bonifico",
    "MP06": "Vaglia cambiario",
    "MP07": "Bollettino bancario",
    "MP08": "Carta di pagamento",
    "MP09": "RID",
    "MP10": "RID utenze",
    "MP11": "RID veloce",
    "MP12": "RIBA",
    "MP13": "MAV",
    "MP14": "Quietanza erario",
    "MP15": "Giroconto su conti di contabilita speciale",
    "MP16": "Domiciliazione bancaria",
    "MP17": "Domiciliazione postale",
    "MP18": "Bollettino di c/c postale",
    "MP19": "SEPA Direct Debit",
    "MP20": "SEPA Direct Debit CORE",
    "MP21": "SEPA Direct Debit B2B",
    "MP22": "Trattenuta su somme gia riscosse",
}

PHYSICAL_COPY_REQUIRED_CODES = {
    "MP02",
    "MP03",
    "MP05",
    "MP06",
    "MP07",
    "MP13",
    "MP14",
    "MP18",
}

PAYMENT_DOCUMENT_TYPE_MAP: Dict[str, str] = {
    "MP01": "contanti",
    "MP02": "assegno",
    "MP03": "assegno",
    "MP04": "contanti",
    "MP05": "bonifico",
    "MP06": "assegno",
    "MP07": "sconosciuto",
    "MP08": "carta",
    "MP09": "rid",
    "MP10": "rid",
    "MP11": "rid",
    "MP12": "sconosciuto",
    "MP13": "mav",
    "MP14": "f24",
    "MP15": "bonifico",
    "MP16": "rid",
    "MP17": "rid",
    "MP18": "sconosciuto",
    "MP19": "rid",
    "MP20": "rid",
    "MP21": "rid",
    "MP22": "sconosciuto",
}


def normalize_payment_method_code(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = raw.strip()
    upper = cleaned.upper()
    if upper in PAYMENT_METHOD_LABELS:
        return upper
    legacy_map = {
        "bonifico": "MP05",
        "assegno": "MP02",
        "contanti": "MP01",
        "rid": "MP09",
        "mav": "MP13",
        "f24": "MP14",
        "carta": "MP08",
    }
    return legacy_map.get(cleaned.lower(), upper)


def is_known_payment_method(code: Optional[str]) -> bool:
    if not code:
        return False
    return code in PAYMENT_METHOD_LABELS


def get_payment_method_label(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    label = PAYMENT_METHOD_LABELS.get(code)
    if not label:
        return code
    return f"{code} - {label}"


def is_physical_copy_required(code: Optional[str]) -> bool:
    if not code:
        return False
    return code in PHYSICAL_COPY_REQUIRED_CODES


def is_instant_payment(code: Optional[str]) -> bool:
    if not code:
        return False
    return code in PAYMENT_METHOD_LABELS and code not in PHYSICAL_COPY_REQUIRED_CODES


def map_payment_method_to_document_type(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    return PAYMENT_DOCUMENT_TYPE_MAP.get(code)


def list_payment_method_choices() -> List[Tuple[str, str]]:
    return [(code, PAYMENT_METHOD_LABELS[code]) for code in PAYMENT_METHOD_LABELS.keys()]


def summarize_payment_methods(codes: Iterable[str]) -> List[str]:
    seen = []
    for code in codes:
        if code not in seen:
            seen.append(code)
    return [get_payment_method_label(code) or code for code in seen if code]
