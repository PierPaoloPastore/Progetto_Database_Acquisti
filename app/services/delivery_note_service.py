"""
Servizi per la gestione dei DDT (DeliveryNote).
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, List, Optional

from werkzeug.utils import secure_filename

from app.models import DeliveryNote, DeliveryNoteLine, LegalEntity
from app.services import scan_service, settings_service
from app.services.unit_of_work import UnitOfWork


logger = logging.getLogger(__name__)

ALLOWED_EXTERNAL_FILE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}


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
        supplier = uow.suppliers.get_by_id(supplier_id)
        if not supplier:
            raise ValueError("Fornitore non valido")
        if legal_entity_id is not None:
            legal_entity = uow.session.query(LegalEntity).get(legal_entity_id)
            if legal_entity is None:
                raise ValueError("Intestatario non valido")

        safe_name, rel_path = _store_uploaded_delivery_note_file(file, ddt_number)

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


def create_external_delivery_note(
    *,
    supplier_id: int,
    legal_entity_id: Optional[int],
    ddt_number: str,
    ddt_date: date,
    external_id: str,
    total_amount: Optional[Decimal] = None,
    notes: Optional[str] = None,
    lines: Optional[list[dict[str, Any]]] = None,
    file=None,
) -> dict[str, Any]:
    """
    Crea un DDT proveniente da GestionaleFitofarmaci.

    - document_id resta null
    - status viene forzato a unmatched
    - source viene forzato a manual
    - import_source contiene l'origine esterna con external_id
    """
    normalized_number = str(ddt_number or "").strip()
    normalized_external_id = str(external_id or "").strip()
    normalized_notes = str(notes or "").strip() or None
    warnings: list[str] = []

    if supplier_id is None:
        raise ValueError("supplier_id obbligatorio")
    if not normalized_number:
        raise ValueError("ddt_number obbligatorio")
    if not ddt_date:
        raise ValueError("ddt_date obbligatoria")
    if not normalized_external_id:
        raise ValueError("external_id obbligatorio")
    if lines is not None and not isinstance(lines, list):
        raise ValueError("lines deve essere una lista di oggetti")

    upload = _normalize_optional_upload(file)
    if upload is not None:
        _validate_external_upload(upload)

    if normalized_notes:
        warnings.append("notes ricevuto ma non persistito: delivery_notes non ha un campo dedicato")

    import_source = f"GestionaleFitofarmaci:{normalized_external_id}"

    with UnitOfWork() as uow:
        supplier = uow.suppliers.get_by_id(supplier_id)
        if not supplier:
            raise LookupError("Fornitore non valido")
        if legal_entity_id is not None:
            legal_entity = uow.session.query(LegalEntity).get(legal_entity_id)
            if legal_entity is None:
                raise LookupError("Intestatario non valido")

        existing = uow.delivery_notes.find_by_identity_and_import_source(
            supplier_id=supplier_id,
            ddt_number=normalized_number,
            ddt_date=ddt_date,
            import_source=import_source,
        )
        if existing is not None:
            logger.info(
                "DDT esterno duplicato rilevato",
                extra={
                    "delivery_note_id": existing.id,
                    "supplier_id": supplier_id,
                    "ddt_number": normalized_number,
                    "ddt_date": ddt_date.isoformat(),
                    "import_source": import_source,
                },
            )
            return {
                "delivery_note": existing,
                "created": False,
                "duplicate": True,
                "warnings": warnings,
            }

        safe_name = None
        rel_path = None
        if upload is not None:
            safe_name, rel_path = _store_uploaded_delivery_note_file(upload, normalized_number)

        note = DeliveryNote(
            document_id=None,
            supplier_id=supplier_id,
            legal_entity_id=legal_entity_id,
            ddt_number=normalized_number,
            ddt_date=ddt_date,
            total_amount=total_amount,
            file_path=rel_path,
            file_name=safe_name,
            source="manual",
            import_source=import_source,
            imported_at=datetime.utcnow(),
            status="unmatched",
        )
        uow.delivery_notes.add(note)
        uow.session.flush()

        if lines:
            _create_delivery_note_lines(note.id, lines, uow)

        uow.commit()
        logger.info(
            "DDT esterno creato",
            extra={
                "delivery_note_id": note.id,
                "supplier_id": supplier_id,
                "legal_entity_id": legal_entity_id,
                "ddt_number": normalized_number,
                "ddt_date": ddt_date.isoformat(),
                "import_source": import_source,
                "has_file": bool(rel_path),
                "lines_count": len(lines or []),
            },
        )
        return {
            "delivery_note": note,
            "created": True,
            "duplicate": False,
            "warnings": warnings,
        }


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
            description = str(entry.get("description") or "").strip()
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
            ln.item_code = str(entry.get("item_code") or "").strip() or None

            def _num(val, cast):
                if val is None or val == "":
                    return None
                try:
                    return cast(val)
                except Exception:
                    return None

            ln.quantity = _num(entry.get("quantity"), Decimal)
            ln.uom = str(entry.get("uom") or "").strip() or None
            ln.amount = _num(entry.get("amount"), Decimal)
            ln.notes = str(entry.get("notes") or "").strip() or None

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


def _remove_delivery_note_file(note: DeliveryNote) -> None:
    if not note or not note.file_path:
        return
    base = settings_service.get_delivery_note_storage_path()
    full_path = settings_service.resolve_storage_path(base, note.file_path)
    try:
        if os.path.exists(full_path):
            os.remove(full_path)
    except OSError:
        pass

    try:
        parts = Path(note.file_path).parts
        if parts:
            year = parts[0]
            if str(year).isdigit():
                archive_dir = settings_service.get_ddt_archive_path(int(year))
                archive_path = os.path.join(archive_dir, Path(note.file_path).name)
                if os.path.exists(archive_path):
                    os.remove(archive_path)
    except OSError:
        pass


def attach_delivery_note_file(note_id: int, file) -> DeliveryNote:
    """Allega o sostituisce il PDF del DDT."""
    if file is None or not getattr(file, "filename", None):
        raise ValueError("File PDF mancante.")

    with UnitOfWork() as uow:
        note = uow.delivery_notes.get_by_id(note_id)
        if not note:
            raise ValueError("DDT non trovato")

        safe_name, rel_path = _store_uploaded_delivery_note_file(file, note.ddt_number)

        _remove_delivery_note_file(note)
        note.file_path = rel_path
        note.file_name = safe_name
        if note.imported_at is None:
            note.imported_at = datetime.utcnow()

        uow.commit()
        return note


def update_delivery_note(
    note_id: int,
    *,
    supplier_id: int,
    legal_entity_id: Optional[int],
    ddt_number: str,
    ddt_date: date,
    total_amount: Optional[Decimal],
    status: Optional[str] = None,
) -> DeliveryNote:
    """Aggiorna i dati anagrafici del DDT."""
    if not ddt_number:
        raise ValueError("Numero DDT obbligatorio")
    if not ddt_date:
        raise ValueError("Data DDT obbligatoria")

    with UnitOfWork() as uow:
        note = uow.delivery_notes.get_by_id(note_id)
        if not note:
            raise ValueError("DDT non trovato")

        supplier = uow.suppliers.get_by_id(supplier_id)
        if not supplier:
            raise ValueError("Fornitore non valido")
        if legal_entity_id is not None:
            legal_entity = uow.session.query(LegalEntity).get(legal_entity_id)
            if legal_entity is None:
                raise ValueError("Intestatario non valido")

        note.supplier_id = supplier_id
        note.legal_entity_id = legal_entity_id
        note.ddt_number = ddt_number
        note.ddt_date = ddt_date
        note.total_amount = total_amount
        if status:
            note.status = status

        uow.commit()
        return note


def delete_delivery_note(note_id: int) -> bool:
    """Elimina un DDT e i file associati."""
    with UnitOfWork() as uow:
        note = uow.delivery_notes.get_by_id(note_id)
        if not note:
            return False

        _remove_delivery_note_file(note)
        uow.delivery_notes.delete(note)
        uow.commit()
        return True


def _normalize_optional_upload(file):
    if file is None:
        return None
    if not getattr(file, "filename", None):
        return None
    return file


def _validate_external_upload(file) -> None:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTERNAL_FILE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTERNAL_FILE_EXTENSIONS))
        raise ValueError(f"Formato file non supportato. Estensioni ammesse: {allowed}")


def _store_uploaded_delivery_note_file(file, ddt_number: str) -> tuple[str, str]:
    original_name = getattr(file, "filename", "") or ""
    suffix = Path(original_name).suffix.lower()
    safe_name = secure_filename(original_name) or f"ddt_{ddt_number}{suffix or '.pdf'}"
    base_path = settings_service.get_delivery_note_storage_path()
    rel_path = scan_service.store_delivery_note_file(
        file=file,
        base_path=base_path,
        filename=safe_name,
    )
    return safe_name, rel_path


def _create_delivery_note_lines(note_id: int, lines_payload: list[dict[str, Any]], uow: UnitOfWork) -> None:
    seen_line_numbers: set[int] = set()
    for idx, entry in enumerate(lines_payload, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"lines[{idx}] non valido: atteso oggetto")

        raw_line_number = entry.get("line_number")
        description = str(entry.get("description") or "").strip()
        if raw_line_number in (None, ""):
            raise ValueError(f"lines[{idx}].line_number obbligatorio")
        try:
            line_number = int(raw_line_number)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"lines[{idx}].line_number non valido") from exc
        if line_number < 1:
            raise ValueError(f"lines[{idx}].line_number deve essere >= 1")
        if not description:
            raise ValueError(f"lines[{idx}].description obbligatoria")
        if line_number in seen_line_numbers:
            raise ValueError(f"lines[{idx}].line_number duplicato nel payload")
        seen_line_numbers.add(line_number)

        line = DeliveryNoteLine(
            delivery_note_id=note_id,
            line_number=line_number,
            description=description,
            item_code=str(entry.get("item_code") or "").strip() or None,
            quantity=_parse_optional_decimal(entry.get("quantity"), f"lines[{idx}].quantity"),
            uom=str(entry.get("uom") or "").strip() or None,
            amount=_parse_optional_decimal(entry.get("amount"), f"lines[{idx}].amount"),
            notes=str(entry.get("notes") or "").strip() or None,
        )
        uow.delivery_note_lines.add(line)


def _parse_optional_decimal(value: Any, field_name: str) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    normalized = str(value).strip().replace(" ", "")
    if not normalized:
        return None
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} non valido") from exc
