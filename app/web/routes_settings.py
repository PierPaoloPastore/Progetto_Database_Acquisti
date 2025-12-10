"""
Route web per la gestione delle impostazioni applicative.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.services.settings_service import get_setting, set_setting


settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.get("/")
def index():
    """
    Pagina principale delle impostazioni (GET).
    Corrisponde all'endpoint 'settings.index'.
    """
    scan_inbox = get_setting("SCAN_INBOX_PATH", "")
    copy_storage = get_setting("PHYSICAL_COPY_STORAGE_PATH", "")

    return render_template(
        "settings/edit.html",
        scan_inbox=scan_inbox,
        copy_storage=copy_storage,
    )


@settings_bp.post("/")
def save_settings():
    """
    Salvataggio delle impostazioni (POST).
    """
    scan_inbox = request.form.get("scan_inbox", "").strip()
    copy_storage = request.form.get("copy_storage", "").strip()

    set_setting("SCAN_INBOX_PATH", scan_inbox)
    set_setting("PHYSICAL_COPY_STORAGE_PATH", copy_storage)

    flash("Impostazioni salvate correttamente", "success")
    
    # FIX: Reindirizza all'endpoint corretto 'settings.index'
    return redirect(url_for("settings.index"))