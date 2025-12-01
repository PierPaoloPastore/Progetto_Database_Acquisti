"""
Route web per la gestione delle impostazioni applicative.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.services import get_setting, set_setting


settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.get("/")
def settings_view():
    inbox = get_setting("SCAN_INBOX_PATH", "")
    storage = get_setting("PHYSICAL_COPY_STORAGE_PATH", "")
    return render_template(
        "settings/settings.html",
        inbox=inbox,
        storage=storage,
    )


@settings_bp.post("/")
def settings_update():
    inbox = request.form.get("inbox_path", "").strip()
    storage = request.form.get("storage_path", "").strip()

    set_setting("SCAN_INBOX_PATH", inbox)
    set_setting("PHYSICAL_COPY_STORAGE_PATH", storage)

    flash("Impostazioni aggiornate correttamente.", "success")
    return redirect(url_for("settings.settings_view"))
