"""Import per file, registro MySQL e staging persistente (protocollo v1)."""
from __future__ import annotations

import hashlib
import copy
import json
import logging
import os
import shutil
import socket
import traceback
from datetime import datetime, timezone
from decimal import Decimal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

from flask import current_app, g

from app.models import Document
from app.parsers.fatturapa_parser import import_metadata
from app.repositories import import_log_repo as registry
from app.services import settings_service
from app.services.unit_of_work import UnitOfWork


class ImportConflict(ValueError):
    def __init__(self, message, document_id=None):
        super().__init__(message)
        self.document_id = document_id


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def operator():
    user = getattr(g, "current_user", None)
    return {"id": getattr(user, "id", None), "name": getattr(user, "username", None),
            "source": type(user).__name__ if user else "unavailable"}


def storage_root():
    return Path(settings_service.get_xml_storage_path()).resolve()


def diagnostic_root():
    return Path(os.environ.get("IMPORT_DIAGNOSTIC_DIR", str(storage_root() / ".import-diagnostics"))).resolve()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sync_directory(path):
    if os.name != "nt":
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=True)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def emit(payload):
    """Un file per processo evita la rotazione concorrente dello stesso JSONL."""
    try:
        folder = diagnostic_root()
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"import-{socket.gethostname()}-{os.getpid()}.jsonl"
        handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        try:
            record = logging.LogRecord("import-audit", logging.INFO, __file__, 0,
                                       json.dumps(payload, ensure_ascii=True), (), None)
            # handleError del logging standard nasconde gli errori: qui devono diventare avvisi.
            def fail(record):
                raise OSError("Diagnostica import non disponibile")
            handler.handleError = fail
            handler.emit(record)
            handler.flush()
        finally:
            handler.close()
        return True
    except Exception:
        return False


def _write_record(session, payload, status):
    row = registry.attempt_log(session, payload["attempt_id"])
    if row is None:
        row = registry.create_import_log(session=session, file_name=payload["file_name"][:255],
                                        import_source="attempt:" + payload["attempt_id"])
    row.file_hash = payload.get("file_hash")
    row.status = status
    row.message = json.dumps(payload, ensure_ascii=True)
    return row


def _manifest(payload):
    return storage_root() / ".import-staging" / payload["attempt_id"] / "manifest.json"


def _checkpoint(payload, phase):
    payload.update(phase=phase, updated_at=utcnow())
    save_json(_manifest(payload), payload)
    if not emit(payload):
        payload.setdefault("warnings", [])
        if "Diagnostica JSONL non disponibile" not in payload["warnings"]:
            payload["warnings"].append("Diagnostica JSONL non disponibile")


def _safe_path(relative):
    root = storage_root()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ImportConflict("Percorso import esterno al deposito")
    return path


def _copy_verified(source, target, digest):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if sha256(target) != digest:
            raise ImportConflict("File già presente con contenuto diverso")
        return
    part = target.with_name(target.name + ".part")
    with source.open("rb") as incoming, part.open("wb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    if sha256(part) != digest:
        raise ImportConflict("Il file è cambiato durante la copia")
    os.replace(part, target)
    sync_directory(target.parent)


def _validate(dtos, metadata):
    if len(dtos) != len(metadata):
        raise ImportConflict("Conteggio corpi XML diverso dal risultato del parser")
    seen = set()
    for dto, meta in zip(dtos, metadata):
        identity = meta["identity"]
        key = json.dumps(identity)
        if key in seen:
            raise ImportConflict("Identità contabile ripetuta nello stesso XML")
        seen.add(key)
        if (dto.invoice_number != identity[3] or not dto.invoice_date or
                dto.invoice_date.isoformat() != identity[4] or dto.tipo_documento != identity[2]):
            raise ImportConflict("Dati identificativi incompleti o alterati dal parser")
        if not dto.lines or not dto.supplier.name:
            raise ValueError("Righe o fornitore mancanti")
        if dto.total_gross_amount is None:
            if dto.total_taxable_amount is None or dto.total_vat_amount is None:
                raise ValueError("Totali insufficienti per registrare la fattura")
            dto.total_gross_amount = dto.total_taxable_amount + dto.total_vat_amount
        amounts = [dto.total_gross_amount, dto.total_taxable_amount, dto.total_vat_amount]
        amounts += [line.total_line_amount for line in dto.lines]
        amounts += [payment.expected_amount for payment in dto.payments]
        if any(value is None or not Decimal(str(value)).is_finite() for value in amounts):
            raise ValueError("Importi mancanti o non validi")


def _snapshot(session, doc):
    snapshot = registry.document_snapshot(session, doc.id)
    if snapshot:
        return snapshot
    if not doc.file_path:
        raise ImportConflict(f"Documento storico #{doc.id}: XML mancante, necessaria revisione")
    try:
        metadata = import_metadata(_safe_path(doc.file_path))
        matching = [m for m in metadata if m["identity"][3] == doc.document_number
                    and m["identity"][4] == doc.document_date.isoformat()]
        if len(matching) == 1:
            return matching[0]
    except Exception:
        pass
    raise ImportConflict(f"Documento storico #{doc.id}: identità non verificabile")


def _duplicate(session, dto, meta, entity_id, file_hash):
    candidates = registry.accounting_candidates(session, dto.invoice_number, dto.invoice_date, meta["identity"])
    matches = []
    for doc in candidates:
        imported = registry.document_snapshot(session, doc.id)
        if imported and imported["identity"] == meta["identity"] and (
                doc.legal_entity_id != entity_id or doc.document_number != dto.invoice_number or doc.document_date != dto.invoice_date):
            raise ImportConflict(f"Documento #{doc.id} modificato dopo l'importazione: verificare l'identità", doc.id)
        if doc.legal_entity_id != entity_id:
            continue
        snapshot = _snapshot(session, doc)
        if snapshot["identity"] != meta["identity"]:
            old, new = snapshot["identity"], meta["identity"]
            if old[2:] == new[2:] and old[0][:2] == new[0][:2] and old[1][:2] == new[1][:2]:
                raise ImportConflict(f"Documento #{doc.id}: identificativi fiscali discordanti, verificare", doc.id)
            continue
        if snapshot["body_hash"] != meta["body_hash"]:
            raise ImportConflict(f"Stessa identità contabile del documento #{doc.id}, contenuto diverso", doc.id)
        if not doc.file_path or not _safe_path(doc.file_path).is_file():
            raise ImportConflict(f"XML del documento #{doc.id} non disponibile: recupero necessario", doc.id)
        if imported and imported.get("stored_hash") and sha256(_safe_path(doc.file_path)) != imported["stored_hash"]:
            raise ImportConflict(f"XML del documento #{doc.id} alterato dopo l'importazione", doc.id)
        if doc.invoice_lines.count() != len(dto.lines) or doc.vat_summaries.count() != len(dto.vat_summaries) or (dto.tipo_documento != "TD04" and doc.payments.count() != len(dto.payments)):
            raise ImportConflict(f"Documento #{doc.id} incompleto: revisione necessaria", doc.id)
        matches.append(doc)
    if len(matches) > 1:
        raise ImportConflict("Più documenti esistenti con la stessa identità contabile")
    if matches:
        doc = matches[0]
        reason = "file_hash" if sha256(_safe_path(doc.file_path)) == file_hash else "document_identity"
        return doc, reason
    return None, None


def _detail(dto, meta, payload, doc=None, reason=None):
    return {"file_name": payload["file_name"], "attempt_id": payload["attempt_id"],
            "batch_id": payload["batch_id"], "document_number": dto.invoice_number,
            "document_date": dto.invoice_date.isoformat() if dto.invoice_date else meta["identity"][4], "supplier_name": dto.supplier.name,
            "legal_entity_name": payload.get("legal_entity_name"),
            "document_data_source": "file importato", "invoice_id": doc.id if doc else None,
            "duplicate_reason": reason, "existing_file_name": doc.file_name if doc else None,
            "existing_document_number": doc.document_number if doc else None,
            "existing_document_date": doc.document_date.isoformat() if doc else None,
            "same_file_name": "si" if doc and (doc.file_name or "").split("#body")[0] == payload["file_name"] else "no",
            **meta}


def _archive(payload):
    source = _safe_path(payload["staged_path"])
    target = Path(payload["archive_path"])
    _copy_verified(source, target, payload["file_hash"])
    # Conserviamo la sorgente: potrebbe essere condivisa con altri documenti/importatori.


def _finish_committed(session, payload):
    """Non crea documenti e non cancella file. Idempotente dopo riavvio."""
    root = storage_root()
    for detail in payload["details"]:
        doc = session.get(Document, detail["invoice_id"])
        if doc is None:
            detail.update(status="conflict", message="Documento eliminato dopo l'importazione")
            payload["state"] = "conflict"
            payload["message"] = "Uno o più documenti sono stati eliminati dopo l'importazione"
            continue
        relative = doc.file_path
        if relative == payload.get("final_path"):
            _copy_verified(_safe_path(payload["staged_path"]), root / relative, payload["file_hash"])
        if not relative or not _safe_path(relative).is_file():
            raise ImportConflict("File definitivo non disponibile")
        expected = detail.get("stored_hash")
        if expected and sha256(_safe_path(relative)) != expected:
            raise ImportConflict("Contenuto del file definitivo non corrispondente")
    try:
        _archive(payload)
    except Exception:
        payload.setdefault("warnings", []).append("Documento registrato; archiviazione originale da completare")
    return payload


def reconcile_attempt(attempt_id):
    """La nuova connessione + il lock attendono la fine del vecchio commit."""
    manifest = storage_root() / ".import-staging" / attempt_id / "manifest.json"
    with registry.import_session() as session:
        row = registry.attempt_log(session, attempt_id)
        registered = registry.read_payload(row) if row else {}
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except FileNotFoundError:
            if not registered:
                raise
            payload = registered
        if registered.get("state") in {"committed", "duplicate"}:
            payload = _finish_committed(session, registered)
            _checkpoint(payload, "reconciled")
        elif registered.get("state") in {"failed", "conflict"}:
            payload = registered
            _checkpoint(payload, "reconciled")
        else:
            # Il lock prova che il vecchio writer non può più committare.
            payload.update(state="failed", error_code="INTERRUPTED",
                           message="Tentativo interrotto senza commit. È possibile riprovare.")
            for detail in payload.get("details", []):
                if not detail.get("duplicate_reason"):
                    detail["invoice_id"] = None
            _write_record(session, payload, "error")
            session.commit()
            _checkpoint(payload, "interrupted")
    return payload


def recover_imports():
    results = []
    attempts = {path.parent.name for path in (storage_root() / ".import-staging").glob("*/manifest.json")}
    try:
        with registry.import_session() as session:
            attempts.update(registry.pending_attempt_ids(session))
    except Exception:
        # I manifest restano consultabili anche quando MySQL è offline.
        pass
    for attempt_id in sorted(attempts):
        path = storage_root() / ".import-staging" / attempt_id / "manifest.json"
        try:
            current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
            if current.get("phase") in {"finished", "reconciled", "interrupted"} and not current.get("warnings"):
                continue
            results.append(reconcile_attempt(attempt_id))
        except Exception:
            results.append({"attempt_id": attempt_id, "state": "reconcile",
                            "message": "Recupero non concluso: database o deposito non disponibili"})
    return results


def import_file(source, batch_id, import_source, archive_base, forced_entity=None):
    from app.services import import_service as service
    upload = source if hasattr(source, "save") else None
    source = Path((upload.filename or "").replace("\\", "/")).name if upload else Path(source)
    source = Path(source)
    attempt_id = str(uuid4())
    payload = {"version": 1, "kind": "attempt", "attempt_id": attempt_id,
               "batch_id": batch_id, "created_at": utcnow(), "instance": socket.gethostname(),
               "app_version": os.environ.get("APP_VERSION", "unknown"), "operator": operator(),
               "file_name": source.name, "source": import_source, "state": "started",
               "details": [], "warnings": []}
    committing = False
    active_detail = None
    try:
        with registry.import_session() as session:
            # Prima prova durevole anche quando il deposito non è raggiungibile.
            _write_record(session, payload, "warning")
            session.commit()
            _checkpoint(payload, "started")
            staged = _manifest(payload).parent / source.name
            payload["staged_path"] = str(staged.relative_to(storage_root()))
            if source.suffix.lower() not in {".xml", ".p7m"}:
                raise ValueError("Formato non supportato: atteso XML o P7M")
            if upload:
                with staged.with_suffix(staged.suffix + ".part").open("wb") as stream:
                    upload.save(stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(staged.with_suffix(staged.suffix + ".part"), staged)
                sync_directory(staged.parent)
                payload["file_hash"] = sha256(staged)
            else:
                payload["file_hash"] = sha256(source)
                _copy_verified(source, staged, payload["file_hash"])
            _checkpoint(payload, "staged")
            metadata = import_metadata(staged)
            dtos = service.parse_invoice_xml(staged, validate_xsd=bool(current_app.config.get("FATTURAPA_VALIDATE_XSD_WARN", False)), logger=current_app.logger)
            payload["details"] = [_detail(dto, meta, payload) for dto, meta in zip(dtos, metadata)]
            _validate(dtos, metadata)
            payload["body_count"] = len(dtos)
            header = service._extract_header_data(staged)
            uow = UnitOfWork(session)
            entity = service._get_or_create_legal_entity(header, session)
            if forced_entity is not None and forced_entity != entity.id:
                raise ImportConflict("Intestazione selezionata diversa dal destinatario XML")
            payload["legal_entity_name"] = entity.name
            payload["legal_entity_id"] = entity.id
            pending = []
            for dto, meta, detail in zip(dtos, metadata, payload["details"]):
                active_detail = detail
                detail["legal_entity_name"] = entity.name
                doc, reason = _duplicate(session, dto, meta, entity.id, payload["file_hash"])
                detail.update(_detail(dto, meta, payload, doc, reason))
                pending.append((dto, meta, doc, detail))
            year = service._resolve_archive_year(dtos)
            archive_dir = Path(archive_base).resolve() / "Archivio" / "XML" / str(year) / attempt_id
            payload["archive_path"] = str(archive_dir / source.name)
            if any(doc is None for _, _, doc, _ in pending):
                filename = service._import_filename(source, dtos)
                final = storage_root() / str(year) / attempt_id / filename
                final.parent.mkdir(parents=True, exist_ok=False)
                payload["final_path"] = str(final.relative_to(storage_root()))
            _checkpoint(payload, "prepared")
            for index, (dto, meta, doc, detail) in enumerate(pending, 1):
                if doc is None:
                    supplier = uow.suppliers.get_or_create_from_dto(dto.supplier)
                    dto.file_name = source.name + (f"#body{index}" if len(dtos) > 1 else "")
                    if str(settings_service.get_setting("IMPORT_DDT_FROM_XML", "1")).lower() not in {"1", "true", "yes", "on"}:
                        dto.delivery_notes = []
                    doc, _ = uow.documents.create_from_fatturapa(
                        invoice_dto=dto, supplier_id=supplier.id, legal_entity_id=entity.id,
                        import_source=import_source)
                    doc.file_path = payload["final_path"]
                    detail.update(invoice_id=doc.id, status="pending", stage="db_write",
                                  message="Documento preparato, commit non ancora confermato", stored_hash=payload["file_hash"])
                    registry.create_import_log(
                        session=session, file_name=dto.file_name, file_hash=payload["file_hash"],
                        import_source=f"attempt:{attempt_id}", status="success", document_id=doc.id,
                        message=json.dumps({"version": 1, "kind": "body", "attempt_id": attempt_id,
                                            "body_index": index, "stored_hash": payload["file_hash"], **meta}))
                else:
                    detail.update(status="skipped", stage="duplicate", stored_hash=sha256(_safe_path(doc.file_path)),
                                  message="Già presente: " + ("stesso contenuto" if detail["duplicate_reason"] == "file_hash" else "stessa identità contabile"))
            session.flush()
            # I vincoli di tutte le righe sono verificati prima della pubblicazione.
            _checkpoint(payload, "publishing")
            if payload.get("final_path"):
                _copy_verified(staged, _safe_path(payload["final_path"]), payload["file_hash"])
            _checkpoint(payload, "published")
            confirmation = copy.deepcopy(payload)
            confirmation["state"] = "committed" if any(d["status"] == "pending" for d in payload["details"]) else "duplicate"
            for detail in confirmation["details"]:
                if detail["status"] == "pending":
                    detail.update(status="success", stage="committed", message="Documento registrato")
            _write_record(session, confirmation, "success" if confirmation["state"] == "committed" else "duplicate")
            _checkpoint(payload, "committing")
            committing = True
            session.commit()
            payload = confirmation
            _finish_committed(session, payload)
            _checkpoint(payload, "finished")
            return payload
    except Exception as exc:
        payload["error_trace"] = [
            {"file": frame.filename, "line": frame.lineno, "function": frame.name}
            for frame in traceback.extract_tb(exc.__traceback__)
        ]
        if committing:
            try:
                return reconcile_attempt(attempt_id)
            except Exception:
                payload.update(state="reconcile", error_code="COMMIT_UNCERTAIN",
                               message="Esito da riconciliare: non reinserire prima della verifica")
        else:
            payload.update(state="conflict" if isinstance(exc, ImportConflict) else "failed",
                           error_code=type(exc).__name__,
                           message=str(exc) if isinstance(exc, (ImportConflict, ValueError)) else "Importazione non completata; verificare deposito e database")
            # Nessun testo SQL/parametro nel registro pubblico.
            payload["cause"] = type(exc).__name__
            original = getattr(exc, "orig", exc)
            payload["error_number"] = getattr(original, "errno", None)
            if payload["error_number"] is None and getattr(original, "args", ()) and isinstance(original.args[0], int):
                payload["error_number"] = original.args[0]
            for detail in payload["details"]:
                if not detail.get("duplicate_reason"):
                    detail["invoice_id"] = None
            if getattr(exc, "document_id", None) and active_detail is not None:
                active_detail["invoice_id"] = exc.document_id
            try:
                with registry.import_session() as session:
                    _write_record(session, payload, "error")
                    session.commit()
            except Exception:
                payload["state"] = "reconcile"
        try:
            _checkpoint(payload, payload["state"])
        except Exception:
            emit(payload)
        return payload


def summarize(payloads, batch_id):
    summary = {"batch_id": batch_id, "total_files": len(payloads), "processed": len(payloads),
               "imported": 0, "skipped": 0, "errors": 0, "warnings": 0, "reconcile": 0,
               "details": [], "attempts": [p["attempt_id"] for p in payloads]}
    for payload in payloads:
        state = payload["state"]
        if state in {"committed", "duplicate"}:
            summary["details"].extend(payload["details"])
            summary["imported"] += sum(d["status"] == "success" for d in payload["details"])
            summary["skipped"] += sum(d["status"] == "skipped" for d in payload["details"])
        else:
            summary["errors"] += 1
            summary["reconcile"] += state == "reconcile"
            details = payload.get("details") or [{"file_name": payload["file_name"], "attempt_id": payload["attempt_id"]}]
            for detail in details:
                summary["details"].append({**detail, "status": state, "stage": payload.get("phase"),
                                           "message": payload.get("message", "Verifica manuale necessaria"),
                                           "error_type": payload.get("error_code")})
        for warning in payload.get("warnings", []):
            summary["warnings"] += 1
            summary["details"].append({"file_name": payload["file_name"], "status": "warning",
                                       "stage": "post_commit", "message": warning})
    summary["narrative"] = (f"{summary['total_files']} file esaminati: {summary['imported']} documenti registrati, "
                            f"{summary['skipped']} già presenti, {summary['errors']} file da controllare, "
                            f"{summary['warnings']} avvisi. Batch {batch_id}.")
    return summary

def batch_summary(batch_id):
    from app.extensions import db
    from sqlalchemy.orm import Session
    with Session(db.engine) as session:
        payloads = registry.batch_attempts(session, batch_id)
        for payload in payloads:
            if payload["state"] not in {"committed", "duplicate"}:
                continue
            for detail in payload["details"]:
                doc = session.get(Document, detail["invoice_id"])
                try:
                    available = doc and doc.file_path and sha256(_safe_path(doc.file_path)) == detail["stored_hash"]
                except (OSError, ValueError):
                    available = False
                if not available:
                    payload.update(state="reconcile", message="Commit registrato; documento o XML da verificare")
    for payload in payloads:
        # Il DB prova il commit; un manifest successivo può indicare un guasto storage.
        try:
            current = json.loads(_manifest(payload).read_text(encoding="utf-8"))
            if current.get("state") == "reconcile":
                payload.update(state="reconcile", message=current.get("message"))
            payload["warnings"] = current.get("warnings", payload.get("warnings", []))
        except (OSError, ValueError):
            if payload["state"] in {"committed", "duplicate"}:
                payload.update(state="reconcile", message="Commit registrato; deposito da verificare")
        if payload["state"] not in {"committed", "duplicate", "failed", "conflict"}:
            payload.update(state="reconcile", message="Operazione in corso o da riconciliare")
    result = summarize(payloads, batch_id)
    from werkzeug.utils import secure_filename
    result["report_paths"] = [str(path) for path in sorted(
        (diagnostic_root() / "reports").glob(f"import_report_*_{secure_filename(batch_id)}_*.csv"))]
    return result
