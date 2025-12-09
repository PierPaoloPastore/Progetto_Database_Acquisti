"""
Repository per il modello ImportLog.

Gestisce le operazioni di lettura/creazione dei log di import dei file XML.
"""

from typing import List, Optional

from app.extensions import db
from app.models import ImportLog


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
    return import_log.document_id if import_log else None


def create_import_log(**kwargs) -> ImportLog:
    """
    Crea un nuovo record di log import e lo aggiunge alla sessione.

    Non esegue il commit.
    """
    log = ImportLog(**kwargs)
    db.session.add(log)
    return log
