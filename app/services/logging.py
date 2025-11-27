"""Helper per logging strutturato JSON nei servizi applicativi."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional


def log_structured_event(
    action: str,
    *,
    message: Optional[str] = None,
    level: str = "info",
    **fields: Any,
) -> None:
    """Registra un evento strutturato sfruttando il logger configurato in ``extensions``.

    Il logging JSON è già configurato a livello di root logger da ``app.extensions``;
    questa funzione è un piccolo wrapper per ridurre la duplicazione di codice nei
    servizi e per evitare che eventuali problemi di serializzazione interrompano il
    flusso applicativo.
    """

    logger = logging.getLogger()
    log_method = getattr(logger, level.lower(), logger.info)

    payload: Dict[str, Any] = {"action": action}
    payload.update(fields)

    try:
        log_method(message or "Structured service event", extra=payload)
    except Exception:
        # Il logging non deve mai interrompere il flusso di business
        logger.debug("Logging strutturato fallito", exc_info=True)
