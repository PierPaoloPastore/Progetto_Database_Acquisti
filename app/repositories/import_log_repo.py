"""
Repository per il modello ImportLog.

Gestisce le operazioni di lettura/creazione dei log di import dei file XML.
"""

from typing import List, Optional
from contextlib import contextmanager
import hashlib
from flask import current_app
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.extensions import db
from app.models import Document, ImportLog


def get_import_log_by_id(log_id: int) -> Optional[ImportLog]:
    """Restituisce un record di import_log dato il suo ID, oppure None se non trovato."""
    return ImportLog.query.get(log_id)


def list_import_logs(limit: int = 500) -> List[ImportLog]:
    """
    Restituisce l'elenco dei log di import, ordinati per data decrescente.

    :param limit: massimo numero di record da restituire.
    """
    query = ImportLog.query.order_by(ImportLog.created_at.desc(), ImportLog.id.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


def list_import_logs_by_file_name(file_name: str) -> List[ImportLog]:
    """Restituisce tutti i log relativi a un determinato file XML."""
    return (
        ImportLog.query.filter_by(file_name=file_name)
        .order_by(ImportLog.created_at.desc())
        .all()
    )


def get_import_log_by_file_hash(file_hash: str) -> Optional[ImportLog]:
    """
    Restituisce il log di import più recente per un determinato file_hash.

    Restituisce solo log che hanno effettivamente creato un documento (document_id non None).
    """
    if not file_hash:
        return None
    return (
        ImportLog.query
        .filter(ImportLog.file_hash == file_hash)
        .filter(ImportLog.document_id.isnot(None))
        .order_by(ImportLog.created_at.desc())
        .first()
    )


def find_document_by_file_hash(file_hash: str) -> Optional[int]:
    """
    Restituisce l'ID del documento associato a un file_hash, se esiste.

    Restituisce None se il file_hash non è mai stato importato con successo.
    """
    import_log = get_import_log_by_file_hash(file_hash)
    if not import_log or not import_log.document_id:
        return None

    document = Document.query.get(import_log.document_id)
    if document is None:
        return None
    return document.id


def create_import_log(*, session=None, **kwargs) -> ImportLog:
    """
    Crea un nuovo record di log import e lo aggiunge alla sessione.

    Non esegue il commit.
    """
    log = ImportLog(**kwargs)
    (session if session is not None else db.session).add(log)
    return log


def read_payload(log):
    import json
    try:
        value = json.loads(log.message or "{}")
        return value if isinstance(value, dict) and value.get("version") == 1 else {}
    except (ValueError, TypeError):
        return {}


def attempt_log(session, attempt_id):
    return session.query(ImportLog).filter_by(
        import_source=f"attempt:{attempt_id}", document_id=None,
    ).order_by(ImportLog.id).first()


def document_snapshot(session, document_id):
    for log in session.query(ImportLog).filter_by(document_id=document_id, status="success").order_by(ImportLog.id.desc()):
        payload = read_payload(log)
        if payload.get("kind") == "body":
            return payload
    return None


def accounting_candidates(session, number, document_date, identity=None):
    # Il confronto fiscale completo avviene sui metadati XML, non sui nomi.
    candidates = session.query(Document).filter(
        Document.document_date == document_date,
        Document.document_number == number,
    ).all()
    # ponytail: scansione lineare JSON; indice dedicato solo se lo storico lo richiede.
    # Anche dopo una modifica manuale il documento conserva l'identità importata.
    if identity:
        for row in session.query(ImportLog).filter(ImportLog.status == "success", ImportLog.document_id.isnot(None)):
            if read_payload(row).get("identity") == identity:
                doc = session.get(Document, row.document_id)
                if doc and doc not in candidates:
                    candidates.append(doc)
    return candidates


def batch_attempts(session, batch_id):
    rows = session.query(ImportLog).filter(
        ImportLog.import_source.like("attempt:%"), ImportLog.document_id.is_(None),
    ).order_by(ImportLog.id).all()
    return [payload for row in rows if (payload := read_payload(row)).get("kind") == "attempt"
            and payload.get("batch_id") == batch_id]


def pending_attempt_ids(session):
    rows = session.query(ImportLog).filter(
        ImportLog.import_source.like("attempt:%"), ImportLog.status == "warning",
        ImportLog.document_id.is_(None),
    )
    return [p["attempt_id"] for row in rows if (p := read_payload(row)).get("kind") == "attempt"]




@contextmanager
def import_session():
    """Lock cooperativo e scritture sulla stessa connessione fisica."""
    engine = db.engine
    mysql = engine.dialect.name == "mysql"
    if not mysql and not current_app.testing:
        raise RuntimeError("Import affidabile richiede MySQL")
    lock_name = "invoice-import:" + hashlib.sha256(str(engine.url.database).encode()).hexdigest()[:40]
    with engine.connect() as connection:
        locked = False
        try:
            if mysql:
                locked = connection.execute(text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name}).scalar() == 1
                connection.commit()
                if not locked:
                    raise TimeoutError("Importazione occupata; riprovare")
                engines = dict(connection.execute(text(
                    "SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"
                )).all())
                required = {"documents", "invoice_lines", "vat_summaries", "payments",
                            "delivery_notes", "suppliers", "legal_entities", "import_logs", "document_audit_logs"}
                if any(engines.get(name) != "InnoDB" for name in required):
                    raise RuntimeError("Tabelle import mancanti o non transazionali")
                connection.commit()
            # ponytail: lock globale per DB; lock per identità solo se serve più throughput.
            with Session(bind=connection, expire_on_commit=False) as session:
                yield session
        finally:
            if mysql and locked:
                try:
                    if connection.invalidated:
                        raise RuntimeError("Connessione del lock persa")
                    connection.rollback()
                    connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                    connection.commit()
                except Exception:
                    connection.invalidate()
