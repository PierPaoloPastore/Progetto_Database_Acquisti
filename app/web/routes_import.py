"""
Route per la gestione dell'import FatturaPA XML.

Comprende:
- schermata di riepilogo/import (GET /import/run)
- esecuzione import (POST /import/run)
"""

from __future__ import annotations

from typing import Optional

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)

from app.services import run_import

import_bp = Blueprint("import", __name__)


@import_bp.route("/run", methods=["GET", "POST"])
def run_view():
    """
    Schermata di esecuzione import.

    GET:
        mostra info sulla cartella import e l'ultimo riepilogo (se presente in sessione)
    POST:
        esegue run_import() e mostra il riepilogo nella stessa pagina
    """
    from flask import session  # import locale per evitare problemi in contesti non-WSGI

    default_folder = current_app.config.get("IMPORT_XML_FOLDER")

    if request.method == "GET":
        last_summary = session.get("last_import_summary")
        return render_template(
            "import/import_run.html",
            default_folder=default_folder,
            summary=last_summary,
        )

    # POST: esecuzione import
    folder_override: Optional[str] = request.form.get("folder") or None
    summary = run_import(folder=folder_override)

    # salvo in sessione per riuscire a rivederlo al reload
    session["last_import_summary"] = summary

    flash(
        f"Import completato. File totali: {summary['total_files']}, "
        f"importati: {summary['imported']}, errori: {summary['errors']}.",
        "info",
    )

    return redirect(url_for("import.run_view"))
