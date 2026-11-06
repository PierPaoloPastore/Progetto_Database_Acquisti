"""Consultazione del registro: aggregazione e presentazione, senza scritture."""
from uuid import UUID

from app.repositories import import_log_repo as registry


LABELS = {"success": "Registrata", "committed": "Registrata",
          "skipped": "Già presente", "duplicate": "Già presente",
          "warning": "Avviso", "failed": "Fallito", "error": "Errore",
          "conflict": "Conflitto", "started": "Esito non confermato",
          "reconcile": "Da verificare"}


def category(state):
    if state in {"success", "committed"}:
        return "success"
    if state in {"skipped", "duplicate"}:
        return "duplicate"
    if state == "warning":
        return "warning"
    return "problems"


def history_page(before=None, search="", outcome="", since=None, until=None, limit=25):
    groups = {}
    # shortcut: scansione JSON lineare; indicizzare i batch se il registro cresce molto.
    for row in registry.history_records():
        payload = registry.read_payload(row)
        if payload.get("kind") == "body":
            continue
        batch_id = None
        try:
            batch_id = str(UUID(payload.get("batch_id", ""))) if payload.get("kind") == "attempt" else None
        except (ValueError, TypeError, AttributeError):
            pass
        key = batch_id or f"legacy:{row.id}"
        group = groups.setdefault(key, {
            "id": row.id, "batch_id": batch_id, "date": row.created_at,
            "files": 0, "imported": 0, "skipped": 0, "errors": 0,
            "warnings": 0, "pending": 0, "matches": False,
            "legacy": not batch_id, "file_name": row.file_name,
            "message": row.message if not payload else payload.get("message", ""),
            "document_id": row.document_id,
        })
        group["files"] += 1
        if row.created_at and (not group["date"] or row.created_at < group["date"]):
            group["date"] = row.created_at
        state = payload.get("state", row.status)
        details = payload.get("details", [])
        if state in {"committed", "duplicate"}:
            group["imported"] += sum(d.get("status") == "success" for d in details)
            group["skipped"] += sum(d.get("status") == "skipped" for d in details) if payload else 1
        elif state in {"success", "skipped"}:
            if state == "success" and not payload and not row.document_id:
                group["pending"] += 1
            else:
                group["imported" if state == "success" else "skipped"] += 1
        elif state in {"failed", "error", "conflict"}:
            group["errors"] += 1
        else:
            group["pending"] += 1
        group["warnings"] += len(payload.get("warnings", [])) or int(state == "warning" and not payload)
        haystack = " ".join([row.file_name or "", row.document_number or ""]
                            + [str(d.get("document_number", "")) for d in details])
        day = row.created_at.date() if row.created_at else None
        group["matches"] |= (search.casefold() in haystack.casefold()
                             and (not since or (day and day >= since))
                             and (not until or (day and day <= until)))
    selected = []
    for group in groups.values():
        if before is not None and group["id"] >= before:
            continue
        if not group["matches"]:
            continue
        if outcome == "problems" and not group["errors"]:
            continue
        if outcome == "warnings" and not group["warnings"]:
            continue
        if outcome == "pending" and not group["pending"]:
            continue
        group["tone"] = "danger" if group["errors"] else "warning" if group["warnings"] or group["pending"] else "success"
        selected.append(group)
    selected.sort(key=lambda g: g["id"], reverse=True)
    return selected[:limit], selected[limit - 1]["id"] if len(selected) > limit else None


def present_summary(summary):
    """Una riga per tentativo; i corpi e i dettagli tecnici restano espandibili."""
    details = summary.get("details", [])
    dates = registry.document_import_dates({d["invoice_id"] for d in details if d.get("invoice_id")})
    groups = {}
    attempt_by_file = {}
    for detail in details:
        if detail.get("attempt_id"):
            attempt_by_file.setdefault(detail.get("file_name"), set()).add(detail["attempt_id"])
    for detail in details:
        if detail.get("status") == "skipped":
            imported = dates.get(detail.get("invoice_id"))
            detail["existing_imported_at"] = imported.strftime("%d/%m/%Y %H:%M:%S UTC") if imported else None
        detail["status_label"] = LABELS.get(detail.get("status"), "Da verificare")
        attempts = attempt_by_file.get(detail.get("file_name"), set())
        key = detail.get("attempt_id") or (next(iter(attempts)) if len(attempts) == 1 else "warning:" + detail.get("file_name", "-"))
        groups.setdefault(key, {"file_name": detail.get("file_name", "-"), "details": []})["details"].append(detail)
    for group in groups.values():
        kinds = {category(d.get("status")) for d in group["details"]}
        group["category"] = next(k for k in ("problems", "warning", "success", "duplicate") if k in kinds)
        group["label"] = {"problems": "Da controllare", "warning": "Avviso", "success": "Registrata", "duplicate": "Già presente"}[group["category"]]
        group["tone"] = {"problems": "danger", "warning": "warning", "success": "success", "duplicate": "secondary"}[group["category"]]
    priority = {"problems": 0, "warning": 1, "success": 2, "duplicate": 3}
    summary["file_groups"] = sorted(groups.values(), key=lambda g: (priority[g["category"]], g["file_name"]))
    return summary
