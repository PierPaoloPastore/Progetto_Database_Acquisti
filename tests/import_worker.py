"""Processo di prova: configurazione esplicita, mai importa config.py."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flask import Flask
from sqlalchemy.orm import Session
from app.extensions import db
from app.services import import_recovery_service as recovery
from app.services import settings_service


def main():
    root, mode, result_name = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    uri = os.environ["IMPORT_WORKER_DATABASE_URL"]
    app = Flask("import-test-worker")
    app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI=uri)
    db.init_app(app)
    checkpoint, commit = recovery._checkpoint, Session.commit
    commits = []

    def crash_checkpoint(payload, phase):
        checkpoint(payload, phase)
        if phase == mode:
            os._exit(73)

    def crash_commit(session):
        commit(session)
        commits.append(1)
        if mode == "committed" and len(commits) == 2:
            os._exit(74)

    with app.app_context(), patch.object(settings_service, "get_xml_storage_path", return_value=str(root / "deposito")), \
            patch.object(settings_service, "get_setting", return_value="1"), \
            patch.object(recovery, "_checkpoint", crash_checkpoint), patch.object(Session, "commit", crash_commit):
        if mode == "recover":
            result = recovery.recover_imports()
        else:
            result = recovery.import_file(root / "originale.xml", "worker-batch", "upload", root / "deposito")
        (root / result_name).write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()
