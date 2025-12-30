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
    default_xsl = get_setting("DEFAULT_XSL_STYLE", "asso")
    ocr_provider = get_setting("OCR_PROVIDER", "local")
    ocrspace_api_key = get_setting("OCRSPACE_API_KEY", "")
    ocrspace_endpoint = get_setting("OCRSPACE_ENDPOINT", "https://api.ocr.space/parse/image")
    ocr_default_lang = get_setting("OCR_DEFAULT_LANG", "ita")
    ocr_max_pages = get_setting("OCR_MAX_PAGES", "5")

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
        ocr_provider=ocr_provider,
        ocrspace_api_key=ocrspace_api_key,
        ocrspace_endpoint=ocrspace_endpoint,
        ocr_default_lang=ocr_default_lang,
        ocr_max_pages=ocr_max_pages,
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
    default_xsl = request.form.get("default_xsl", "asso").strip() or "asso"
    ocr_provider = request.form.get("ocr_provider", "local").strip() or "local"
    ocrspace_api_key = request.form.get("ocrspace_api_key", "").strip()
    ocrspace_endpoint = request.form.get("ocrspace_endpoint", "").strip()
    ocr_default_lang = request.form.get("ocr_default_lang", "ita").strip() or "ita"
    ocr_max_pages = request.form.get("ocr_max_pages", "").strip()

    set_setting("SCAN_INBOX_PATH", scan_inbox)
    set_setting("XML_INBOX_PATH", xml_inbox)
    set_setting("PAYMENT_INBOX_PATH", payment_inbox)
    set_setting("PHYSICAL_COPY_STORAGE_PATH", copy_storage)
    set_setting("XML_STORAGE_PATH", xml_storage)
    set_setting("PAYMENT_FILES_STORAGE_PATH", payment_storage)
    set_setting("DELIVERY_NOTE_STORAGE_PATH", ddt_storage)
    set_setting("DEFAULT_XSL_STYLE", default_xsl)
    set_setting("OCR_PROVIDER", ocr_provider)
    set_setting("OCRSPACE_API_KEY", ocrspace_api_key)
    set_setting("OCRSPACE_ENDPOINT", ocrspace_endpoint)
    set_setting("OCR_DEFAULT_LANG", ocr_default_lang)
    set_setting("OCR_MAX_PAGES", ocr_max_pages)

    flash("Impostazioni salvate correttamente", "success")
    
    # FIX: Reindirizza all'endpoint corretto 'settings.index'
    return redirect(url_for("settings.index"))
