"""
Route per la gestione dell'import FatturaPA XML.

Comprende:
- schermata di riepilogo/import (GET /import/run)
- esecuzione import via upload cartella (POST /import/run)
"""

from __future__ import annotations

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)

from app.services import run_import_files
from app.services.settings_service import get_xml_inbox_path

import_bp = Blueprint("import", __name__)


def _wants_json_response() -> bool:
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = request.headers.get("Accept", "") or ""
    return "application/json" in accept.lower()


@import_bp.route("/run", methods=["GET", "POST"])
def run_view():
    """
    Schermata di esecuzione import.

    GET:
        mostra info sulla cartella import e l'ultimo riepilogo (se presente in sessione)
    POST:
        esegue l'import dai file caricati e mostra il riepilogo nella stessa pagina
    """
    from flask import session  # import locale per evitare problemi in contesti non-WSGI

    default_folder = get_xml_inbox_path()

    if request.method == "GET":
        last_summary = session.get("last_import_summary")
        return render_template(
            "import/import_run.html",
            default_folder=default_folder,
            summary=last_summary,
        )

    # POST: esecuzione import
    files = request.files.getlist("files")
    if not files or not any(f.filename for f in files):
        flash("Seleziona una cartella con file XML/P7M da importare.", "warning")
        return redirect(url_for("import.run_view"))

    summary = run_import_files(files=files)

    # salvo in sessione per riuscire a rivederlo al reload
    session["last_import_summary"] = summary
    if _wants_json_response():
        return jsonify(summary)

    flash(
        f"Import completato. File totali: {summary['total_files']}, "
        f"importati: {summary['imported']}, errori: {summary['errors']}.",
        "info",
    )

    return redirect(url_for("import.run_view"))
