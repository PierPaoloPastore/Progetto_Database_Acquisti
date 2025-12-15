"""
Servizi per la gestione dei Documenti (ex Invoices).
Rifattorizzato con Pattern Unit of Work.
"""
from __future__ import annotations

import os
from datetime import date, datetime
from typing import Optional, List, Any

from flask import current_app

from app.services.unit_of_work import UnitOfWork
from app.services.dto import DocumentSearchFilters

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
            
            # Gestione date
            doc_date_str = form_data.get("document_date")
            if doc_date_str:
                doc.document_date = _parse_date(doc_date_str)
            
            # Cambio stato
            doc.doc_status = "verified"
            
            uow.commit()
            return True, "Documento confermato"

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
            "import_logs": doc.import_logs
        }

def update_document_status(document_id: int, doc_status: str, due_date: Optional[date] = None):
    with UnitOfWork() as uow:
        doc = uow.documents.get_by_id(document_id)
        if doc:
            if doc_status:
                doc.doc_status = doc_status
            if due_date:
                doc.due_date = due_date
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
            doc.doc_status = "rejected"
            uow.commit()
        return doc

def list_documents_to_review(order: str = "desc", document_type: Optional[str] = None):
    with UnitOfWork() as uow:
        return uow.documents.list_imported(document_type=document_type, order=order)

def get_next_document_to_review(order: str = "desc", document_type: Optional[str] = None):
    with UnitOfWork() as uow:
        return uow.documents.get_next_imported(document_type=document_type, order=order)

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
            
            upload_folder = current_app.config.get("UPLOAD_FOLDER", "storage/uploads")
            
            ref_date = doc.document_date or date.today()
            year_str = str(ref_date.year)
            month_str = f"{ref_date.month:02d}"
            
            save_dir = os.path.join(upload_folder, "scans", year_str, month_str)
            os.makedirs(save_dir, exist_ok=True)
            
            new_filename = f"doc_{doc.id}_{filename}"
            full_path = os.path.join(save_dir, new_filename)
            
            file.save(full_path)
            
            rel_path = os.path.join("scans", year_str, month_str, new_filename)
            doc.physical_copy_file_path = rel_path

        uow.commit()
        return doc

def list_documents_without_physical_copy():
    return []

def render_invoice_html(xml_path: str, xsl_path: str) -> str:
    import lxml.etree as ET
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