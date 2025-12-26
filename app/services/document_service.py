"""
Servizi per la gestione dei Documenti (ex Invoices).
Rifattorizzato con Pattern Unit of Work.
"""
from __future__ import annotations

import os
import shutil
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Any

from app.services.unit_of_work import UnitOfWork
from app.services import settings_service
from app.services.settings_service import get_attachments_storage_path
import json
from app.services.dto import DocumentSearchFilters
from app.models import Document

class DocumentService:
    """
    Facade per le operazioni sui documenti, usando UnitOfWork.
    """

    @staticmethod
    def get_document_by_id(document_id: int):
        with UnitOfWork() as uow:
            return uow.documents.get_by_id(document_id)

    @staticmethod
    def review_and_confirm(document_id: int, form_data: dict) -> tuple[bool, str]:
        """
        Esegue la revisione e conferma di un documento importato.
        """
        with UnitOfWork() as uow:
            doc = uow.documents.get_by_id(document_id)
            if not doc:
                return False, "Documento non trovato"

            # Aggiornamento campi base
            doc.document_number = form_data.get("document_number")
            doc.document_date = _parse_date(form_data.get("document_date"))
            doc.registration_date = _parse_date(form_data.get("registration_date"))
            doc.due_date = _parse_date(form_data.get("due_date"))
            doc.note = form_data.get("note") or None

            # Importi
            doc.total_taxable_amount = _parse_decimal(form_data.get("total_taxable_amount"))
            doc.total_vat_amount = _parse_decimal(form_data.get("total_vat_amount"))
            doc.total_gross_amount = _parse_decimal(form_data.get("total_gross_amount"))

            # Cambio stato: conferma => verified di default
            chosen_status = form_data.get("doc_status") or None
            allowed_statuses = {"pending_physical_copy", "verified", "archived"}
            if not chosen_status or chosen_status not in allowed_statuses:
                chosen_status = "verified"
            doc.doc_status = chosen_status
            
            uow.commit()
            return True, "Documento confermato"

    @staticmethod
    def delete_document(document_id: int) -> bool:
        with UnitOfWork() as uow:
            doc = uow.documents.get_by_id(document_id)
            if not doc:
                return False
            uow.documents.delete(doc)
            uow.commit()
            return True

# --- Funzioni Helper ---

def get_accounting_years() -> List[int]:
    """Recupera gli anni fiscali presenti."""
    with UnitOfWork() as uow:
        return uow.documents.list_accounting_years()

def search_documents(
    filters: DocumentSearchFilters, 
    limit: int = 200, 
    document_type: Optional[str] = None
) -> List[Any]:
    with UnitOfWork() as uow:
        return uow.documents.search(
            document_type=document_type,
            date_from=filters.date_from,
            date_to=filters.date_to,
            document_number=filters.document_number,
            supplier_id=filters.supplier_id,
            doc_status=filters.doc_status,
            payment_status=filters.payment_status,
            physical_copy_status=filters.physical_copy_status,
            legal_entity_id=filters.legal_entity_id,
            accounting_year=filters.accounting_year,
            min_total=filters.min_total,
            max_total=filters.max_total,
            limit=limit,
        )

def get_document_detail(document_id: int) -> Optional[dict]:
    with UnitOfWork() as uow:
        doc = uow.documents.get_by_id(document_id)
        if not doc:
            return None
        
        payments = uow.payments.get_by_document_id(document_id)
        
        return {
            "invoice": doc,
            "lines": doc.lines,
            "vat_summaries": doc.vat_summaries,
            "payments": payments,
            "import_logs": doc.import_logs,
            "supplier": doc.supplier,
            "attachments": list_document_attachments(document_id),
        }


def list_document_attachments(document_id: int) -> list[dict]:
    base_dir = get_attachments_storage_path()
    meta_path = os.path.join(base_dir, str(document_id), "attachments.json")
    if not os.path.exists(meta_path):
        return []
    try:
        with open(meta_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def create_manual_document(form_data: dict) -> tuple[bool, str, Optional[int]]:
    allowed_types = {"f24", "insurance", "mav", "cbill", "receipt", "rent", "tax", "other"}
    doc_type = (form_data.get("document_type") or "").strip()
    if doc_type not in allowed_types:
        return False, "Tipo documento non supportato.", None

    allowed_statuses = {"pending_physical_copy", "verified", "archived"}
    doc_status = (form_data.get("doc_status") or "verified").strip()
    if doc_status not in allowed_statuses:
        doc_status = "verified"

    supplier_id = _parse_int(form_data.get("supplier_id"))
    legal_entity_id = _parse_int(form_data.get("legal_entity_id"))

    taxable = _parse_decimal(form_data.get("total_taxable_amount"))
    vat = _parse_decimal(form_data.get("total_vat_amount"))
    gross = _parse_decimal(form_data.get("total_gross_amount"))
    if gross is None:
        gross = (taxable or Decimal("0")) + (vat or Decimal("0"))

    doc = Document(
        document_type=doc_type,
        supplier_id=supplier_id,
        legal_entity_id=legal_entity_id,
        document_number=form_data.get("document_number") or None,
        document_date=_parse_date(form_data.get("document_date")),
        registration_date=_parse_date(form_data.get("registration_date")),
        due_date=_parse_date(form_data.get("due_date")),
        total_taxable_amount=taxable,
        total_vat_amount=vat,
        total_gross_amount=gross,
        note=form_data.get("note") or None,
        doc_status=doc_status,
        is_paid=_parse_bool(form_data.get("is_paid")),
    )

    if doc_type == "f24":
        doc.f24_period_from = _parse_date(form_data.get("f24_period_from"))
        doc.f24_period_to = _parse_date(form_data.get("f24_period_to"))
        doc.f24_tax_type = form_data.get("f24_tax_type") or None
        doc.f24_payment_code = form_data.get("f24_payment_code") or None
    elif doc_type == "insurance":
        doc.insurance_policy_number = form_data.get("insurance_policy_number") or None
        doc.insurance_coverage_start = _parse_date(form_data.get("insurance_coverage_start"))
        doc.insurance_coverage_end = _parse_date(form_data.get("insurance_coverage_end"))
        doc.insurance_type = form_data.get("insurance_type") or None
        doc.insurance_asset_description = form_data.get("insurance_asset_description") or None
    elif doc_type in {"mav", "cbill"}:
        doc.payment_code = form_data.get("payment_code") or None
        doc.creditor_entity = form_data.get("creditor_entity") or None
    elif doc_type == "receipt":
        doc.receipt_merchant = form_data.get("receipt_merchant") or None
        doc.receipt_category = form_data.get("receipt_category") or None
    elif doc_type == "rent":
        doc.rent_period_month = _parse_int(form_data.get("rent_period_month"))
        doc.rent_period_year = _parse_int(form_data.get("rent_period_year"))
        doc.rent_property_description = form_data.get("rent_property_description") or None
    elif doc_type == "tax":
        doc.tax_type = form_data.get("tax_type") or None
        doc.tax_period_year = _parse_int(form_data.get("tax_period_year"))
        doc.tax_period_description = form_data.get("tax_period_description") or None

    with UnitOfWork() as uow:
        uow.documents.add(doc)
        uow.commit()

    return True, "Documento creato manualmente.", doc.id


def update_document_status(document_id: int, doc_status: str, due_date: Optional[date] = None, note: Optional[str] = None):
    with UnitOfWork() as uow:
        doc = uow.documents.get_by_id(document_id)
        if doc:
            if doc_status:
                doc.doc_status = doc_status
            if due_date:
                doc.due_date = due_date
            if note is not None:
                doc.note = note or None
            uow.commit()
        return doc

def confirm_document(document_id: int):
    with UnitOfWork() as uow:
        doc = uow.documents.get_by_id(document_id)
        if doc:
            doc.doc_status = "verified"
            uow.commit()
        return doc

def reject_document(document_id: int):
    with UnitOfWork() as uow:
        doc = uow.documents.get_by_id(document_id)
        if doc:
            doc.doc_status = "archived"
            uow.commit()
    return doc

def delete_document(document_id: int) -> bool:
    return DocumentService.delete_document(document_id)

def list_documents_to_review(order: str = "desc", document_type: Optional[str] = None, legal_entity_id: Optional[int] = None):
    with UnitOfWork() as uow:
        return uow.documents.list_imported(
            document_type=document_type,
            order=order,
            legal_entity_id=legal_entity_id,
            doc_status="pending_physical_copy",
        )

def get_next_document_to_review(order: str = "desc", document_type: Optional[str] = None, legal_entity_id: Optional[int] = None):
    with UnitOfWork() as uow:
        return uow.documents.get_next_imported(
            document_type=document_type,
            order=order,
            legal_entity_id=legal_entity_id,
            doc_status="pending_physical_copy",
        )

def count_documents_to_review_by_legal_entity() -> dict[int | None, int]:
    """Ritorna un mapping legal_entity_id -> count di documenti in revisione."""
    with UnitOfWork() as uow:
        rows = uow.documents.count_imported_by_legal_entity()
        counts = {}
        for le_id, cnt in rows:
            counts[le_id] = cnt
        return counts

def request_physical_copy(document_id: int):
    with UnitOfWork() as uow:
        doc = uow.documents.get_by_id(document_id)
        if doc:
            doc.physical_copy_status = "requested"
            doc.physical_copy_requested_at = datetime.now()
            uow.commit()
        return doc

def mark_physical_copy_received(document_id: int, file=None):
    with UnitOfWork() as uow:
        doc = uow.documents.get_by_id(document_id)
        if not doc:
            return None

        doc.physical_copy_status = "received"
        doc.physical_copy_received_at = datetime.now()

        if file:
            from werkzeug.utils import secure_filename
            filename = secure_filename(file.filename)

            ref_date = doc.document_date or date.today()
            year_str = str(ref_date.year)
            base_dir = settings_service.get_documents_storage_path()
            save_dir = os.path.join(base_dir, year_str)
            os.makedirs(save_dir, exist_ok=True)

            new_filename = f"doc_{doc.id}_{filename}" if filename else f"doc_{doc.id}"
            safe_name = settings_service.ensure_unique_filename(save_dir, new_filename)
            full_path = os.path.join(save_dir, safe_name)

            file.save(full_path)

            rel_path = os.path.join(year_str, safe_name)
            doc.physical_copy_file_path = rel_path

            archive_dir = settings_service.get_documents_archive_path(ref_date.year)
            archive_name = settings_service.ensure_unique_filename(archive_dir, safe_name)
            shutil.copy2(full_path, os.path.join(archive_dir, archive_name))

        uow.commit()
        return doc

def list_documents_without_physical_copy():
    return []

def render_invoice_html(xml_path: str, xsl_path: str) -> str:
    import lxml.etree as ET
    from pathlib import Path
    from lxml.etree import XMLSyntaxError
    from app.parsers.fatturapa_parser import _extract_xml_from_p7m, _clean_xml_bytes

    def _parse_xml_bytes(xml_bytes: bytes) -> ET._ElementTree:
        try:
            root = ET.fromstring(xml_bytes)
            return ET.ElementTree(root)
        except XMLSyntaxError as exc:
            if "not proper UTF-8" in str(exc):
                enc_attempts = [
                    ("cp1252", "strict", False),
                    ("latin-1", "strict", False),
                    ("cp1252", "replace", True),
                    ("latin-1", "replace", True),
                ]
                for enc, mode, use_recover in enc_attempts:
                    try:
                        text = xml_bytes.decode(enc, errors=mode)
                        utf8_bytes = _clean_xml_bytes(text.encode("utf-8", errors="strict"))
                        if use_recover:
                            parser_recover = ET.XMLParser(recover=True)
                            root = ET.fromstring(utf8_bytes, parser=parser_recover)
                        else:
                            root = ET.fromstring(utf8_bytes)
                        return ET.ElementTree(root)
                    except Exception:
                        continue
            parser_recover = ET.XMLParser(recover=True)
            root = ET.fromstring(xml_bytes, parser=parser_recover)
            return ET.ElementTree(root)

    xml_path_obj = Path(xml_path)
    if xml_path_obj.suffix.lower() == ".p7m":
        xml_bytes = _extract_xml_from_p7m(xml_path_obj)
        dom = _parse_xml_bytes(xml_bytes)
    else:
        dom = ET.parse(xml_path)
    xslt = ET.parse(xsl_path)
    transform = ET.XSLT(xslt)
    newdom = transform(dom)
    return str(newdom)

def _parse_date(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _parse_decimal(value: Optional[str]) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except Exception:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _parse_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
