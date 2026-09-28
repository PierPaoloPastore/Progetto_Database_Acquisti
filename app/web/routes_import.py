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
    send_file,
    abort,
)
from pathlib import Path
from uuid import UUID, uuid4
from app.services.import_recovery_service import batch_summary, diagnostic_root

from app.services import run_import, run_import_files
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

    if request.method == "GET":
        last_batch = request.args.get("batch_id") or session.get("last_import_batch")
        if last_batch:
            try:
                last_batch = str(UUID(last_batch))
            except ValueError:
                abort(400)
        last_summary = batch_summary(last_batch) if last_batch else None
        last_folder = session.get("last_import_folder")
        return render_template(
            "import/import_run.html",
            server_folder=last_folder or "",
            summary=last_summary,
        )

    try:
        batch_id = str(UUID(request.form.get("batch_id"))) if request.form.get("batch_id") else str(uuid4())
    except ValueError:
        abort(400)
    session["last_import_batch"] = batch_id
    session.pop("last_import_summary", None)
    # POST: esecuzione import
    action = (request.form.get("import_action") or request.form.get("action") or "").strip()
    if action == "server_folder":
        server_folder = (request.form.get("server_folder") or "").strip()
        if not server_folder:
            flash("Inserisci un percorso server valido.", "warning")
            return redirect(url_for("import.run_view"))
        summary = run_import(folder=server_folder, batch_id=batch_id)
        session["last_import_batch"] = batch_id
        session["last_import_folder"] = server_folder
        if _wants_json_response():
            return jsonify(_with_links(summary))
        flash(summary["narrative"], "warning" if summary["errors"] else "info")
        return redirect(url_for("import.run_view"))

    files = request.files.getlist("files")
    if not files or not any(f.filename for f in files):
        flash("Seleziona una cartella con file XML/P7M da importare.", "warning")
        return redirect(url_for("import.run_view"))

    summary = run_import_files(files=files, batch_id=batch_id)

    # salvo in sessione per riuscire a rivederlo al reload
    session["last_import_batch"] = batch_id
    if _wants_json_response():
        return jsonify(_with_links(summary))

    flash(summary["narrative"], "warning" if summary["errors"] else "info")

    return redirect(url_for("import.run_view"))


@import_bp.get("/report")
def report_view():
    path_value = (request.args.get("path") or "").strip()
    if not path_value:
        abort(404)

    base_dir = Path(__file__).resolve().parents[2]
    report_dir = (diagnostic_root() / "reports").resolve()
    candidate = (base_dir / path_value).resolve()

    if not candidate.is_file():
        abort(404)
    legacy_reports = (base_dir / "import_debug" / "import_reports").resolve()
    if not any(candidate.is_relative_to(root) for root in (report_dir, legacy_reports)):
        abort(404)

    return send_file(candidate, mimetype="text/csv", as_attachment=False, download_name=candidate.name)


@import_bp.get("/status/<uuid:batch_id>")
def status_view(batch_id):
    return jsonify(_with_links(batch_summary(str(batch_id))))


@import_bp.get("/history")
def history_view():
    from app.repositories.import_log_repo import import_history_page, read_payload
    before = request.args.get("before", type=int)
    file_name = request.args.get("file", "").strip()
    rows = import_history_page(before, file_name)
    entries = []
    for row in rows[:50]:
        payload = read_payload(row)
        batch_id = None
        try:
            batch_id = str(UUID(payload.get("batch_id", "")))
        except (ValueError, TypeError, AttributeError):
            pass
        entries.append({"log": row, "payload": payload, "batch_id": batch_id})
    return render_template("import/history.html", entries=entries, file_name=file_name,
                           next_id=rows[49].id if len(rows) > 50 else None)

def _with_links(summary):
    for detail in summary.get("details", []):
        if detail.get("invoice_id"):
            detail["document_url"] = url_for("documents.detail_view", document_id=detail["invoice_id"])
    return summary
