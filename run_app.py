"""
Avvio rapido dell'app Flask con un singolo comando:

    python run_app.py

Usa la factory create_app() e la configurazione di sviluppo di default.
Nota: l'attivazione dell'ambiente virtuale (.venv) va fatta prima di eseguire
questo script (non può essere gestita in modo portabile da qui).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app import create_app
from config import DevConfig


def main() -> None:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))

    app = create_app(DevConfig)
    host = os.environ.get("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_RUN_PORT", "5000"))

    app.logger.info("Avvio dell'applicazione tramite run_app.py", extra={"component": "launcher"})
    app.run(host=host, port=port, debug=app.config.get("DEBUG", False))


if __name__ == "__main__":
    main()
