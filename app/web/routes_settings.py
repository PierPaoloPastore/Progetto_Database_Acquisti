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
    xml_inbox = get_setting("XML_INBOX_PATH", "")
    payment_inbox = get_setting("PAYMENT_INBOX_PATH", "")
    copy_storage = get_setting("PHYSICAL_COPY_STORAGE_PATH", "")
    xml_storage = get_setting("XML_STORAGE_PATH", "")
    payment_storage = get_setting("PAYMENT_FILES_STORAGE_PATH", "")
    ddt_storage = get_setting("DELIVERY_NOTE_STORAGE_PATH", "")
    default_xsl = get_setting("DEFAULT_XSL_STYLE", "ordinaria")

    return render_template(
        "settings/edit.html",
        scan_inbox=scan_inbox,
        xml_inbox=xml_inbox,
        payment_inbox=payment_inbox,
        copy_storage=copy_storage,
        xml_storage=xml_storage,
        payment_storage=payment_storage,
        ddt_storage=ddt_storage,
        default_xsl=default_xsl,
    )


@settings_bp.post("/")
def save_settings():
    """
    Salvataggio delle impostazioni (POST).
    """
    scan_inbox = request.form.get("scan_inbox", "").strip()
    xml_inbox = request.form.get("xml_inbox", "").strip()
    payment_inbox = request.form.get("payment_inbox", "").strip()
    copy_storage = request.form.get("copy_storage", "").strip()
    xml_storage = request.form.get("xml_storage", "").strip()
    payment_storage = request.form.get("payment_storage", "").strip()
    ddt_storage = request.form.get("ddt_storage", "").strip()
    default_xsl = request.form.get("default_xsl", "ordinaria").strip() or "ordinaria"

    set_setting("SCAN_INBOX_PATH", scan_inbox)
    set_setting("XML_INBOX_PATH", xml_inbox)
    set_setting("PAYMENT_INBOX_PATH", payment_inbox)
    set_setting("PHYSICAL_COPY_STORAGE_PATH", copy_storage)
    set_setting("XML_STORAGE_PATH", xml_storage)
    set_setting("PAYMENT_FILES_STORAGE_PATH", payment_storage)
    set_setting("DELIVERY_NOTE_STORAGE_PATH", ddt_storage)
    set_setting("DEFAULT_XSL_STYLE", default_xsl)

    flash("Impostazioni salvate correttamente", "success")
    
    # FIX: Reindirizza all'endpoint corretto 'settings.index'
    return redirect(url_for("settings.index"))
