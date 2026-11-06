"""Generazione e conferma degli estratti conto, con audit transazionale."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from app.models import DocumentAuditLog
from app.services import payment_service
from app.services.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


class ScheduleConflict(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _amount(value) -> str:
    return str(Decimal(str(value or 0)).quantize(Decimal("0.01")))


def _snapshot(document) -> dict:
    return {
        "id": document.id,
        "document_number": document.document_number,
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "due_date": document.due_date.isoformat() if document.due_date else None,
        "supplier_id": document.supplier_id,
        "supplier_name": document.supplier.name if document.supplier else "Senza fornitore",
        "supplier_iban": document.supplier.iban if document.supplier else None,
        "legal_entity_id": document.legal_entity_id,
        "legal_entity_name": document.legal_entity.name if document.legal_entity else "Senza intestatario",
        "total_gross_amount": _amount(document.total_gross_amount),
        "total_taxable_amount": _amount(document.total_taxable_amount),
        "remaining_amount": _amount(document.remaining_amount),
        "print_status": document.print_status or "not_printed",
        "is_paid": bool(document.is_paid),
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


def _add_event(uow, action: str, payload: dict, document_id=None):
    # L'audit e il flag devono riuscire o fallire nella stessa transazione.
    return uow.document_audit_logs.add(DocumentAuditLog(
        document_id=document_id,
        action=action,
        payload=json.dumps(payload, ensure_ascii=True),
    ))


def _emit(action: str, payload: dict) -> None:
    logger.info("Audit scadenziario", extra={"schedule_event": action, **payload})


def record_generation(rows: list[dict], pdf_bytes: bytes, actor: dict, schedule_id: str) -> int:
    document_ids = [row["doc"].id for row in rows]
    payload = {
        "schedule_id": schedule_id,
        "source": "schedule_print",
        "actor": actor,
        "status": "pending",
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
    }
    with UnitOfWork() as uow:
        event = _add_event(uow, "schedule_gen", payload)
        uow.session.flush()
        audit_id = event.id
        # Una riga per fattura evita di riempire il campo TEXT con estratti grandi.
        items = [_add_event(uow, "schedule_item", {
            "schedule_id": schedule_id, "generation_id": audit_id,
            "source": "schedule_print", "actor": actor, "document": _snapshot(row["doc"]),
        }, row["doc"].id) for row in rows]
        uow.session.flush()
        payload["document_audit_ids"] = [item.id for item in items]
        event.payload = json.dumps(payload, ensure_ascii=True)
        uow.commit()
    _emit("generated", {"generation_id": audit_id, **payload, "document_ids": document_ids})
    return audit_id


def _generation_documents(uow, payload: dict) -> list[dict]:
    items = uow.document_audit_logs.get_by_ids(payload["document_audit_ids"])
    if len(items) != len(payload["document_audit_ids"]) or any(item.action != "schedule_item" for item in items):
        raise ScheduleConflict("Audit dell'estratto incompleto. Genera nuovamente il PDF.")
    records = [json.loads(item.payload) for item in items]
    if any(record.get("schedule_id") != payload["schedule_id"] for record in records):
        raise ScheduleConflict("Audit dell'estratto incoerente. Genera nuovamente il PDF.")
    return [record["document"] for record in records]


def generation_documents(payload: dict) -> list[dict]:
    with UnitOfWork() as uow:
        return _generation_documents(uow, payload)


def record_failure(document_ids: list[int], actor: dict, reason: str, schedule_id: str) -> None:
    payload = {"schedule_id": schedule_id, "source": "schedule_print", "actor": actor,
               "document_ids": document_ids, "reason": reason}
    with UnitOfWork() as uow:
        _add_event(uow, "schedule_failed", payload)
        uow.commit()
    _emit("failed", payload)


def _load_generation(uow, generation_id: int, actor: dict, *, for_update: bool):
    repository = uow.document_audit_logs
    generation = repository.get_for_update(generation_id) if for_update else repository.get_by_id(generation_id)
    if not generation or generation.action != "schedule_gen":
        raise ScheduleConflict("Estratto conto non trovato. Genera nuovamente il PDF.")
    payload = json.loads(generation.payload)
    if payload["actor"]["session_id"] != actor["session_id"]:
        raise ScheduleConflict("Conferma l'estratto conto dalla sessione che lo ha generato.")
    return generation, payload


def preview_generation(generation_id: int, actor: dict) -> dict:
    with UnitOfWork() as uow:
        _, payload = _load_generation(uow, generation_id, actor, for_update=False)
        return {"schedule_id": payload["schedule_id"], "documents": _generation_documents(uow, payload)}


def finish_generation(generation_id: int, actor: dict, *, confirm: bool) -> dict:
    with UnitOfWork() as uow:
        generation, payload = _load_generation(uow, generation_id, actor, for_update=True)
        snapshots = _generation_documents(uow, payload)
        document_ids = [row["id"] for row in snapshots]
        expected_status = "confirmed" if confirm else "cancelled"
        if payload["status"] == expected_status:
            return {"schedule_id": payload["schedule_id"], "count": len(document_ids), "already_done": True}
        if payload["status"] != "pending":
            raise ScheduleConflict("Questo estratto conto è già stato chiuso. Genera nuovamente il PDF.")

        event_payload = {"schedule_id": payload["schedule_id"], "generation_id": generation_id,
                         "source": "schedule_confirm" if confirm else "schedule_cancel", "actor": actor}
        if confirm:
            documents = uow.documents.get_by_ids_for_update(document_ids)
            payment_service.attach_payment_amounts(documents)
            current = {doc.id: _snapshot(doc) for doc in documents}
            if any(current.get(row["id"]) != row or current[row["id"]]["is_paid"]
                   for row in snapshots):
                raise ScheduleConflict("Le fatture sono cambiate dopo la generazione. Genera nuovamente il PDF.")
            for document in documents:
                _add_event(uow, "schedule_confirm", {
                    **event_payload,
                    "document_number": document.document_number,
                    "before": {"print_status": document.print_status},
                    "after": {"print_status": "programmed"},
                }, document.id)
                document.print_status = "programmed"
        else:
            _add_event(uow, "schedule_cancel", {**event_payload, "document_ids": document_ids})

        # Lo snapshot iniziale rimane intatto; l'esito blocca conferme ripetute.
        payload = {**payload, "status": expected_status, "closed_at": _now(), "closed_by": actor}
        generation.payload = json.dumps(payload, ensure_ascii=True)
        uow.commit()
    _emit(expected_status, {**event_payload, "document_ids": document_ids})
    return {"schedule_id": payload["schedule_id"], "count": len(document_ids), "already_done": False}


def unprogram_documents(document_ids: list[int], actor: dict) -> int:
    with UnitOfWork() as uow:
        documents = uow.documents.get_by_ids_for_update(document_ids)
        for document in documents:
            _add_event(uow, "schedule_unmark", {
                "source": "schedule_unprogram", "actor": actor,
                "document_number": document.document_number,
                "before": {"print_status": document.print_status},
                "after": {"print_status": "not_printed"},
            }, document.id)
            document.print_status = "not_printed"
        updated_ids = [doc.id for doc in documents]
        uow.commit()
    _emit("unprogrammed", {"source": "schedule_unprogram", "actor": actor, "document_ids": updated_ids})
    return len(updated_ids)
