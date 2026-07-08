"""
Generazione XML SEPA/CBI per disposizioni di bonifico.

La prima implementazione espone un profilo generico ISO 20022 pain.001.001.03.
I profili bancari specifici possono estendere o sostituire le regole qui definite.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence
from xml.etree import ElementTree as ET

from app.models import BankAccount, Document
from app.services.bank_account_service import normalize_iban


_DECIMAL_ZERO = Decimal("0.00")
_ISO_DATETIME_SECONDS = "%Y-%m-%dT%H:%M:%S"


class CbiExportError(ValueError):
    """Errore di validazione leggibile dall'utente prima della generazione XML."""


@dataclass(frozen=True)
class CbiProfile:
    code: str
    label: str
    pain_version: str
    namespace: str
    service_level_code: str = "SEPA"
    payment_method: str = "TRF"
    charge_bearer: str = "SLEV"
    batch_booking: bool = True


GENERIC_PAIN001_PROFILE = CbiProfile(
    code="generic_pain001",
    label="Generico SEPA pain.001.001.03",
    pain_version="pain.001.001.03",
    namespace="urn:iso:std:iso:20022:tech:xsd:pain.001.001.03",
)

CBI_PROFILES = {
    GENERIC_PAIN001_PROFILE.code: GENERIC_PAIN001_PROFILE,
}


@dataclass(frozen=True)
class CbiExportResult:
    xml_bytes: bytes
    filename: str
    profile: CbiProfile
    transaction_count: int
    control_sum: Decimal


@dataclass(frozen=True)
class _TransferRow:
    document: Document
    supplier_name: str
    creditor_iban: str
    amount: Decimal
    remittance: str


def get_cbi_profile(code: str | None = None) -> CbiProfile:
    profile_code = (code or GENERIC_PAIN001_PROFILE.code).strip()
    return CBI_PROFILES.get(profile_code, GENERIC_PAIN001_PROFILE)


def generate_cbi_xml(
    *,
    documents: Sequence[Document],
    debtor_account: BankAccount,
    execution_date: date | None = None,
    profile_code: str | None = None,
    created_at: datetime | None = None,
) -> CbiExportResult:
    """Genera un XML pain.001 per i documenti selezionati."""
    profile = get_cbi_profile(profile_code)
    now = created_at or datetime.now()
    requested_execution_date = execution_date or date.today()
    rows = _build_transfer_rows(documents)
    debtor_iban = _require_valid_iban(debtor_account.iban, "IBAN ordinante non valido.")
    debtor_name = _clean_text(
        getattr(getattr(debtor_account, "legal_entity", None), "name", None)
        or debtor_account.name
        or "ORDINANTE",
        max_length=70,
    )
    legal_entity_id = getattr(debtor_account, "legal_entity_id", None)
    document_entity_ids = {doc.legal_entity_id for doc in documents if doc.legal_entity_id is not None}
    if len(document_entity_ids) > 1:
        raise CbiExportError("Seleziona documenti della stessa intestazione per generare un file CBI.")
    if document_entity_ids and legal_entity_id not in document_entity_ids:
        raise CbiExportError("Il conto ordinante selezionato non appartiene all'intestazione dei documenti.")

    transaction_count = len(rows)
    control_sum = sum((row.amount for row in rows), _DECIMAL_ZERO).quantize(Decimal("0.01"))
    message_id = f"CBI-{now:%Y%m%d%H%M%S}"
    payment_info_id = f"{message_id}-P1"

    ET.register_namespace("", profile.namespace)
    root = ET.Element(_tag(profile, "Document"))
    init = ET.SubElement(root, _tag(profile, "CstmrCdtTrfInitn"))

    group_header = ET.SubElement(init, _tag(profile, "GrpHdr"))
    _child(group_header, profile, "MsgId", message_id)
    _child(group_header, profile, "CreDtTm", now.strftime(_ISO_DATETIME_SECONDS))
    _child(group_header, profile, "NbOfTxs", str(transaction_count))
    _child(group_header, profile, "CtrlSum", _format_amount(control_sum))
    initiating_party = ET.SubElement(group_header, _tag(profile, "InitgPty"))
    _child(initiating_party, profile, "Nm", debtor_name)

    payment_info = ET.SubElement(init, _tag(profile, "PmtInf"))
    _child(payment_info, profile, "PmtInfId", payment_info_id)
    _child(payment_info, profile, "PmtMtd", profile.payment_method)
    _child(payment_info, profile, "BtchBookg", "true" if profile.batch_booking else "false")
    _child(payment_info, profile, "NbOfTxs", str(transaction_count))
    _child(payment_info, profile, "CtrlSum", _format_amount(control_sum))

    payment_type_info = ET.SubElement(payment_info, _tag(profile, "PmtTpInf"))
    service_level = ET.SubElement(payment_type_info, _tag(profile, "SvcLvl"))
    _child(service_level, profile, "Cd", profile.service_level_code)

    _child(payment_info, profile, "ReqdExctnDt", requested_execution_date.isoformat())
    debtor = ET.SubElement(payment_info, _tag(profile, "Dbtr"))
    _child(debtor, profile, "Nm", debtor_name)
    debtor_account_el = ET.SubElement(payment_info, _tag(profile, "DbtrAcct"))
    debtor_account_id = ET.SubElement(debtor_account_el, _tag(profile, "Id"))
    _child(debtor_account_id, profile, "IBAN", debtor_iban)
    debtor_agent = ET.SubElement(payment_info, _tag(profile, "DbtrAgt"))
    debtor_financial_institution = ET.SubElement(debtor_agent, _tag(profile, "FinInstnId"))
    debtor_other = _child(debtor_financial_institution, profile, "Othr")
    _child(debtor_other, profile, "Id", "NOTPROVIDED")
    _child(payment_info, profile, "ChrgBr", profile.charge_bearer)

    for index, row in enumerate(rows, start=1):
        _append_transfer(payment_info, profile, message_id, index, row)

    _indent(root)
    xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return CbiExportResult(
        xml_bytes=xml_bytes,
        filename=f"cbi_generico_{now:%Y%m%d_%H%M%S}.xml",
        profile=profile,
        transaction_count=transaction_count,
        control_sum=control_sum,
    )


def _build_transfer_rows(documents: Sequence[Document]) -> list[_TransferRow]:
    if not documents:
        raise CbiExportError("Seleziona almeno un documento.")

    rows: list[_TransferRow] = []
    for document in documents:
        supplier = document.supplier
        supplier_name = _clean_text(getattr(supplier, "name", None), max_length=70)
        if not supplier_name:
            raise CbiExportError(f"Fornitore mancante per il documento {document.id}.")

        creditor_iban = _require_valid_iban(
            getattr(supplier, "iban", None),
            f"IBAN fornitore mancante o non valido per {supplier_name}.",
        )
        amount = _document_remaining_amount(document)
        if amount <= _DECIMAL_ZERO:
            raise CbiExportError(f"Il documento {document.document_number or document.id} non ha residuo da pagare.")

        rows.append(
            _TransferRow(
                document=document,
                supplier_name=supplier_name,
                creditor_iban=creditor_iban,
                amount=amount,
                remittance=_build_remittance(document),
            )
        )
    return rows


def _append_transfer(parent, profile: CbiProfile, message_id: str, index: int, row: _TransferRow) -> None:
    tx = ET.SubElement(parent, _tag(profile, "CdtTrfTxInf"))
    payment_id = ET.SubElement(tx, _tag(profile, "PmtId"))
    _child(payment_id, profile, "InstrId", f"{message_id}-{index:04d}")
    _child(payment_id, profile, "EndToEndId", _end_to_end_id(row.document, index))

    amount = ET.SubElement(tx, _tag(profile, "Amt"))
    instructed = ET.SubElement(amount, _tag(profile, "InstdAmt"))
    instructed.set("Ccy", "EUR")
    instructed.text = _format_amount(row.amount)

    creditor_agent = ET.SubElement(tx, _tag(profile, "CdtrAgt"))
    creditor_financial_institution = ET.SubElement(creditor_agent, _tag(profile, "FinInstnId"))
    creditor_other = _child(creditor_financial_institution, profile, "Othr")
    _child(creditor_other, profile, "Id", "NOTPROVIDED")

    creditor = ET.SubElement(tx, _tag(profile, "Cdtr"))
    _child(creditor, profile, "Nm", row.supplier_name)

    creditor_account = ET.SubElement(tx, _tag(profile, "CdtrAcct"))
    creditor_account_id = ET.SubElement(creditor_account, _tag(profile, "Id"))
    _child(creditor_account_id, profile, "IBAN", row.creditor_iban)

    remittance = ET.SubElement(tx, _tag(profile, "RmtInf"))
    _child(remittance, profile, "Ustrd", row.remittance)


def _document_remaining_amount(document: Document) -> Decimal:
    raw_value = getattr(document, "remaining_amount", None)
    if raw_value is None:
        raw_value = document.total_gross_amount
    return Decimal(str(raw_value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _build_remittance(document: Document) -> str:
    parts = ["Pagamento fattura"]
    if document.document_number:
        parts.append(str(document.document_number))
    if document.document_date:
        parts.append(f"del {document.document_date.isoformat()}")
    return _clean_text(" ".join(parts), max_length=140) or "Pagamento fattura"


def _end_to_end_id(document: Document, index: int) -> str:
    number = _clean_identifier(document.document_number or str(document.id))
    if not number:
        number = str(index)
    return f"DOC{document.id}-{number}"[:35]


def _require_valid_iban(raw_iban: str | None, message: str) -> str:
    iban = normalize_iban(raw_iban)
    if not iban or not _is_valid_iban(iban):
        raise CbiExportError(message)
    return iban


def _is_valid_iban(iban: str) -> bool:
    if len(iban) < 15 or len(iban) > 34 or not iban[:2].isalpha() or not iban[2:4].isdigit():
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = ""
    for char in rearranged:
        if char.isdigit():
            numeric += char
        elif char.isalpha():
            numeric += str(ord(char) - 55)
        else:
            return False
    try:
        return int(numeric) % 97 == 1
    except ValueError:
        return False


def _clean_text(value: str | None, *, max_length: int) -> str:
    cleaned = " ".join(str(value or "").replace("\n", " ").replace("\r", " ").split())
    allowed_chars = []
    for char in cleaned:
        if char.isalnum() or char in " /-?:().,'+":
            allowed_chars.append(char)
        else:
            allowed_chars.append(" ")
    return " ".join("".join(allowed_chars).split())[:max_length]


def _clean_identifier(value: str | None) -> str:
    return "".join(char for char in str(value or "") if char.isalnum())[:24]


def _format_amount(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}"


def _tag(profile: CbiProfile, name: str) -> str:
    return f"{{{profile.namespace}}}{name}"


def _child(parent, profile: CbiProfile, name: str, text: str | None = None):
    element = ET.SubElement(parent, _tag(profile, name))
    if text is not None:
        element.text = text
    return element


def _indent(element, level: int = 0) -> None:
    indent_text = "\n" + level * "  "
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indent_text + "  "
        for child in element:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indent_text
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indent_text
