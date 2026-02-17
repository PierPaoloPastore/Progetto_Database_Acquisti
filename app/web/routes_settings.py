"""
Route web per la gestione delle impostazioni applicative.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.services.settings_service import get_setting, set_setting
from app.services.maintenance_service import initialize_database, cleanup_physical_copies


settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.get("/")
def index():
    """
    Pagina principale delle impostazioni (GET).
    Corrisponde all'endpoint 'settings.index'.
    """
    copy_storage = get_setting("PHYSICAL_COPY_STORAGE_PATH", "")
    xml_storage = get_setting("XML_STORAGE_PATH", "")
    payment_storage = get_setting("PAYMENT_FILES_STORAGE_PATH", "")
    ddt_storage = get_setting("DELIVERY_NOTE_STORAGE_PATH", "")
    import_ddt_from_xml = get_setting("IMPORT_DDT_FROM_XML", "1")
    import_ddt_from_xml = str(import_ddt_from_xml).strip().lower() in {"1", "true", "yes", "on"}
    default_xsl = get_setting("DEFAULT_XSL_STYLE", "asso")
    ocr_provider = get_setting("OCR_PROVIDER", "local")
    ocrspace_api_key = get_setting("OCRSPACE_API_KEY", "")
    ocrspace_endpoint = get_setting("OCRSPACE_ENDPOINT", "https://api.ocr.space/parse/image")
    ocr_default_lang = get_setting("OCR_DEFAULT_LANG", "ita")
    ocr_max_pages = get_setting("OCR_MAX_PAGES", "5")
    schedule_soon_days = get_setting("SCHEDULE_SOON_DAYS", "7")
    schedule_group_by_supplier = get_setting("SCHEDULE_GROUP_BY_SUPPLIER", "0")
    schedule_group_by_supplier = str(schedule_group_by_supplier).strip().lower() in {"1", "true", "yes", "on"}
    format_thousands_separator = get_setting("FORMAT_THOUSANDS_SEPARATOR", "0")
    format_thousands_separator = str(format_thousands_separator).strip().lower() in {"1", "true", "yes", "on"}

    return render_template(
        "settings/edit.html",
        copy_storage=copy_storage,
        xml_storage=xml_storage,
        payment_storage=payment_storage,
        ddt_storage=ddt_storage,
        import_ddt_from_xml=import_ddt_from_xml,
        default_xsl=default_xsl,
        ocr_provider=ocr_provider,
        ocrspace_api_key=ocrspace_api_key,
        ocrspace_endpoint=ocrspace_endpoint,
        ocr_default_lang=ocr_default_lang,
        ocr_max_pages=ocr_max_pages,
        schedule_soon_days=schedule_soon_days,
        schedule_group_by_supplier=schedule_group_by_supplier,
        format_thousands_separator=format_thousands_separator,
    )


@settings_bp.post("/")
def save_settings():
    """
    Salvataggio delle impostazioni (POST).
    """
    copy_storage = request.form.get("copy_storage", "").strip()
    xml_storage = request.form.get("xml_storage", "").strip()
    payment_storage = request.form.get("payment_storage", "").strip()
    ddt_storage = request.form.get("ddt_storage", "").strip()
    import_ddt_from_xml = request.form.get("import_ddt_from_xml", "1").strip()
    default_xsl = request.form.get("default_xsl", "asso").strip() or "asso"
    ocr_provider = request.form.get("ocr_provider", "local").strip() or "local"
    ocrspace_api_key = request.form.get("ocrspace_api_key", "").strip()
    ocrspace_endpoint = request.form.get("ocrspace_endpoint", "").strip()
    ocr_default_lang = request.form.get("ocr_default_lang", "ita").strip() or "ita"
    ocr_max_pages = request.form.get("ocr_max_pages", "").strip()
    schedule_soon_days = request.form.get("schedule_soon_days", "").strip()
    schedule_group_by_supplier = request.form.get("schedule_group_by_supplier", "0").strip()
    schedule_group_by_supplier = "1" if schedule_group_by_supplier == "1" else "0"
    format_thousands_separator = request.form.get("format_thousands_separator", "0").strip()
    format_thousands_separator = "1" if format_thousands_separator == "1" else "0"
    import_ddt_from_xml = "1" if import_ddt_from_xml == "1" else "0"

    set_setting("PHYSICAL_COPY_STORAGE_PATH", copy_storage)
    set_setting("XML_STORAGE_PATH", xml_storage)
    set_setting("PAYMENT_FILES_STORAGE_PATH", payment_storage)
    set_setting("DELIVERY_NOTE_STORAGE_PATH", ddt_storage)
    set_setting("IMPORT_DDT_FROM_XML", import_ddt_from_xml)
    set_setting("DEFAULT_XSL_STYLE", default_xsl)
    set_setting("OCR_PROVIDER", ocr_provider)
    set_setting("OCRSPACE_API_KEY", ocrspace_api_key)
    set_setting("OCRSPACE_ENDPOINT", ocrspace_endpoint)
    set_setting("OCR_DEFAULT_LANG", ocr_default_lang)
    set_setting("OCR_MAX_PAGES", ocr_max_pages)
    set_setting("SCHEDULE_SOON_DAYS", schedule_soon_days)
    set_setting("SCHEDULE_GROUP_BY_SUPPLIER", schedule_group_by_supplier)
    set_setting("FORMAT_THOUSANDS_SEPARATOR", format_thousands_separator)

    flash("Impostazioni salvate correttamente", "success")
    
    # FIX: Reindirizza all'endpoint corretto 'settings.index'
    return redirect(url_for("settings.index"))


@settings_bp.post("/initialize-db")
def initialize_db():
    """
    Inizializza il database eliminando i dati applicativi.
    """
    confirm_text = (request.form.get("confirm_text") or "").strip().upper()
    confirm_check = (request.form.get("confirm_check") or "") == "1"
    preserve_settings = (request.form.get("preserve_settings") or "1") == "1"
    preserve_users = (request.form.get("preserve_users") or "1") == "1"
    cleanup_physical = (request.form.get("cleanup_physical_copies") or "") == "1"

    if not confirm_check or confirm_text != "INIZIALIZZA":
        flash("Conferma non valida. Operazione annullata.", "warning")
        return redirect(url_for("settings.index"))

    try:
        cleaned_count = initialize_database(
            preserve_settings=preserve_settings,
            preserve_users=preserve_users,
        )
    except Exception as exc:
        flash(f"Errore durante l'inizializzazione: {exc}", "danger")
        return redirect(url_for("settings.index"))

    cleanup_summary = None
    if cleanup_physical:
        try:
            cleanup_summary = cleanup_physical_copies()
        except Exception as exc:
            flash(f"Database inizializzato, ma pulizia copie fisiche fallita: {exc}", "warning")
            cleanup_summary = None

    message = f"Database inizializzato. Tabelle ripulite: {cleaned_count}."
    if cleanup_summary:
        if cleanup_summary.get("skipped"):
            message += " Deposito copie fisiche non trovato."
        else:
            removed = cleanup_summary.get("removed_files", 0)
            message += f" Copie fisiche eliminate: {removed}."

    flash(message, "success")
    return redirect(url_for("settings.index"))
