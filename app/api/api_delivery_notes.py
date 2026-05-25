"""
API JSON/multipart per i DDT interni.
"""

from __future__ import annotations

import hmac
import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from flask import Blueprint, current_app, jsonify, request

from app.services.delivery_note_service import create_external_delivery_note


api_delivery_notes_bp = Blueprint("api_delivery_notes", __name__)


def _parse_date(value: Any) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_optional_int(value: Any, field_name: str) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} non valido") from exc


def _parse_required_int(value: Any, field_name: str) -> int:
    parsed = _parse_optional_int(value, field_name)
    if parsed is None:
        raise ValueError(f"{field_name} obbligatorio")
    return parsed


def _parse_optional_decimal(value: Any, field_name: str) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    normalized = str(value).strip().replace(" ", "")
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} non valido") from exc


def _configured_token() -> str:
    return (os.environ.get("INTERNAL_API_TOKEN") or "").strip()


def _provided_token() -> str:
    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return (request.headers.get("X-Internal-API-Key") or "").strip()


def _authorize_request() -> None:
    expected = _configured_token()
    if not expected:
        current_app.logger.error("INTERNAL_API_TOKEN non configurato per endpoint DDT interno.")
        raise RuntimeError("Token interno non configurato")

    provided = _provided_token()
    if not provided or not hmac.compare_digest(provided, expected):
        current_app.logger.warning(
            "Tentativo non autorizzato su endpoint DDT interno.",
            extra={"path": request.path, "remote_addr": request.remote_addr},
        )
        raise PermissionError("Token mancante o non valido")


def _load_request_payload() -> tuple[dict[str, Any], Any]:
    content_type = (request.content_type or "").lower()
    if "multipart/form-data" in content_type:
        raw_payload = request.form.get("payload")
        if not raw_payload:
            raise ValueError("payload mancante")
        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ValueError("payload JSON non valido") from exc
        if not isinstance(data, dict):
            raise ValueError("payload deve essere un oggetto JSON")
        return data, request.files.get("file")

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Payload JSON non valido o mancante")
    return data, None


@api_delivery_notes_bp.route("/internal/delivery-notes", methods=["POST"])
def api_create_internal_delivery_note():
    try:
        _authorize_request()
    except PermissionError:
        return jsonify({"success": False, "message": "Token mancante o non valido.", "payload": None}), 401
    except RuntimeError as exc:
        return jsonify({"success": False, "message": str(exc), "payload": None}), 500

    try:
        data, file = _load_request_payload()

        supplier_id = _parse_required_int(data.get("supplier_id"), "supplier_id")
        legal_entity_id = _parse_optional_int(data.get("legal_entity_id"), "legal_entity_id")
        ddt_number = str(data.get("ddt_number") or "").strip()
        external_id = str(data.get("external_id") or "").strip()
        ddt_date = _parse_date(data.get("ddt_date"))
        if not ddt_number:
            raise ValueError("ddt_number obbligatorio")
        if not ddt_date:
            raise ValueError("ddt_date obbligatoria o non valida")
        if not external_id:
            raise ValueError("external_id obbligatorio")

        total_amount = _parse_optional_decimal(data.get("total_amount"), "total_amount")
        notes = data.get("notes")
        lines = data.get("lines")

        result = create_external_delivery_note(
            supplier_id=supplier_id,
            legal_entity_id=legal_entity_id,
            ddt_number=ddt_number,
            ddt_date=ddt_date,
            external_id=external_id,
            total_amount=total_amount,
            notes=notes,
            lines=lines,
            file=file,
        )
        note = result["delivery_note"]
        created = bool(result["created"])
        duplicate = bool(result["duplicate"])
        warnings = result.get("warnings") or []

        status_code = 201 if created else 200
        message = "DDT creato con successo." if created else "DDT giÃ  presente."
        return jsonify(
            {
                "success": True,
                "message": message,
                "payload": {
                    "delivery_note_id": note.id,
                    "created": created,
                    "duplicate": duplicate,
                    "status": note.status,
                    "document_id": note.document_id,
                    "source": note.source,
                    "import_source": note.import_source,
                    "file_name": note.file_name,
                    "warnings": warnings,
                },
            }
        ), status_code
    except ValueError as exc:
        current_app.logger.warning(
            "Payload non valido su endpoint DDT interno.",
            extra={"error": str(exc), "path": request.path},
        )
        return jsonify({"success": False, "message": str(exc), "payload": None}), 400
    except LookupError as exc:
        return jsonify({"success": False, "message": str(exc), "payload": None}), 404
    except Exception as exc:
        current_app.logger.exception(
            "Errore interno creazione DDT da GestionaleFitofarmaci.",
            extra={"path": request.path, "error": str(exc)},
        )
        return jsonify({"success": False, "message": "Errore interno.", "payload": None}), 500
