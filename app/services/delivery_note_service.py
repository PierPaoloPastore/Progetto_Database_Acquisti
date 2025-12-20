"""
Servizi per la gestione dei DDT (DeliveryNote).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from werkzeug.utils import secure_filename

from app.models import DeliveryNote, LegalEntity, DeliveryNoteLine
from app.services.unit_of_work import UnitOfWork
from app.services import settings_service, scan_service


def list_delivery_notes(
    search_term: Optional[str] = None,
    supplier_id: Optional[int] = None,
    legal_entity_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[DeliveryNote]:
    """Restituisce i DDT per la UI."""
    with UnitOfWork() as uow:
        return uow.delivery_notes.list_for_ui(
            search_term=search_term,
            supplier_id=supplier_id,
            legal_entity_id=legal_entity_id,
            status=status,
            limit=limit,
        )


def get_delivery_note(note_id: int) -> Optional[DeliveryNote]:
    with UnitOfWork() as uow:
        return uow.delivery_notes.get_by_id(note_id)


def get_delivery_note_with_lines(note_id: int) -> Optional[DeliveryNote]:
    with UnitOfWork() as uow:
        note = (
            uow.session.query(DeliveryNote)
            .filter(DeliveryNote.id == note_id)
            .options()
            .first()
        )
        if not note:
            return None
        # Eager load lines ordered
        note.delivery_note_lines = uow.delivery_note_lines.list_by_delivery_note(note_id)
        return note


def list_delivery_notes_by_document(document_id: int) -> List[DeliveryNote]:
    with UnitOfWork() as uow:
        return uow.delivery_notes.list_by_document(document_id)


def create_delivery_note(
    *,
    supplier_id: int,
    legal_entity_id: Optional[int],
    ddt_number: str,
    ddt_date: date,
    total_amount: Optional[Decimal],
    file,
    source: str = "pdf_import",
    status: str = "unmatched",
) -> DeliveryNote:
    """
    Registra un nuovo DDT a partire da un upload PDF.
    """
    if not ddt_number:
        raise ValueError("Numero DDT obbligatorio")
    if not ddt_date:
        raise ValueError("Data DDT obbligatoria")
    if file is None or not getattr(file, "filename", None):
        raise ValueError("File PDF DDT obbligatorio")

    with UnitOfWork() as uow:
        # Validazioni base (esistono gli FK?)
        supplier = uow.suppliers.get_by_id(supplier_id)
        if not supplier:
            raise ValueError("Fornitore non valido")
        if legal_entity_id:
            legal_entity = uow.session.query(LegalEntity).get(legal_entity_id)
            if legal_entity is None:
                raise ValueError("Intestatario non valido")

        base_path = settings_service.get_delivery_note_storage_path()
        safe_name = secure_filename(file.filename) or f"ddt_{ddt_number}.pdf"
        rel_path = scan_service.store_delivery_note_file(
            file=file,
            base_path=base_path,
            filename=safe_name,
        )

        note = DeliveryNote(
            supplier_id=supplier_id,
            legal_entity_id=legal_entity_id,
            ddt_number=ddt_number,
            ddt_date=ddt_date,
            total_amount=total_amount,
            file_path=rel_path,
            file_name=safe_name,
            source=source or "pdf_import",
            import_source="manual_upload",
            imported_at=datetime.utcnow(),
            status=status or "unmatched",
        )

        uow.delivery_notes.add(note)
        uow.commit()
        return note


def upsert_delivery_note_lines(note_id: int, lines_payload: list[dict]) -> DeliveryNote:
    """
    Aggiorna/crea le righe di un DDT rimpiazzando quelle esistenti non presenti nel payload.
    lines_payload: list of dicts with optional id, required line_number, description, and optional item_code/quantity/uom/amount/notes.
    """
    with UnitOfWork() as uow:
        note = uow.delivery_notes.get_by_id(note_id)
        if not note:
            raise ValueError("DDT non trovato")

        existing = {ln.id: ln for ln in uow.delivery_note_lines.list_by_delivery_note(note_id)}
        seen_ids = set()

        for entry in lines_payload:
            line_id = entry.get("id")
            line_number = entry.get("line_number")
            description = (entry.get("description") or "").strip()
            if not line_number:
                continue
            if not description:
                continue

            if line_id and line_id in existing:
                ln = existing[line_id]
                seen_ids.add(line_id)
            else:
                ln = DeliveryNoteLine(delivery_note_id=note_id)
                uow.delivery_note_lines.add(ln)

            ln.line_number = int(line_number)
            ln.description = description
            ln.item_code = (entry.get("item_code") or "").strip() or None

            def _num(val, cast):
                if val is None or val == "":
                    return None
                try:
                    return cast(val)
                except Exception:
                    return None

            ln.quantity = _num(entry.get("quantity"), Decimal)
            ln.uom = (entry.get("uom") or "").strip() or None
            ln.amount = _num(entry.get("amount"), Decimal)
            ln.notes = (entry.get("notes") or "").strip() or None

        # Delete lines not seen
        for line_id, ln in existing.items():
            if line_id not in seen_ids and line_id is not None:
                uow.delivery_note_lines.delete(ln)

        uow.commit()
        return note


def find_delivery_note_candidates(
    supplier_id: int,
    ddt_number: Optional[str] = None,
    ddt_date: Optional[date] = None,
    allowed_statuses: Optional[List[str]] = None,
    limit: int = 200,
    exclude_document_ids: Optional[List[int]] = None,
) -> List[DeliveryNote]:
    """Ritorna i DDT candidati al matching dato un supplier + numero (+ data)."""
    with UnitOfWork() as uow:
        return uow.delivery_notes.find_candidates_for_match(
            supplier_id=supplier_id,
            ddt_number=ddt_number,
            ddt_date=ddt_date,
            allowed_statuses=allowed_statuses,
            limit=limit,
            exclude_document_ids=exclude_document_ids,
        )


def link_delivery_note_to_document(delivery_note_id: int, document_id: int, status: str = "matched") -> Optional[DeliveryNote]:
    """
    Collega un DDT a un documento, impostando document_id e stato (default matched).
    """
    with UnitOfWork() as uow:
        note = uow.delivery_notes.get_by_id(delivery_note_id)
        if not note:
            return None
        note.document_id = document_id
        note.status = status
        uow.commit()
        return note


def get_delivery_note_file_path(note: DeliveryNote) -> Optional[str]:
    """Costruisce il percorso assoluto per il file PDF di un DDT."""
    if not note or not note.file_path:
        return None
    base = settings_service.get_delivery_note_storage_path()
    return settings_service.resolve_storage_path(base, note.file_path)
