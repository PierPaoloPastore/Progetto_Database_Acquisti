"""
Route per la gestione dei Documenti.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import io
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional
from flask import (
    Blueprint, render_template, render_template_string, request, redirect, url_for, flash, abort, send_file, current_app, jsonify
)

from app.models import Document
from app.services import document_service as doc_service, ocr_service
from app.services.document_service import DocumentService, render_invoice_html
from app.services.ocr_mapping_service import parse_manual_document_fields
from app.services.formatting_service import format_amount
from app.services.dto import DocumentSearchFilters

# FIX: Import dai service invece che dai repo diretti dove possibile
from app.services.supplier_service import list_active_suppliers
from app.repositories.legal_entity_repo import list_legal_entities
from app.services.delivery_note_service import (
    find_delivery_note_candidates,
    list_delivery_notes_by_document,
    link_delivery_note_to_document,
)

documents_bp = Blueprint("documents", __name__)

ALLOWED_PHYSICAL_COPY_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tif", "tiff"}
_HIGHLIGHT_TRUE_VALUES = {"1", "true", "yes", "on"}

def _is_allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_PHYSICAL_COPY_EXTENSIONS

def _parse_date(value: str) -> Optional[datetime.date]:
    if not value: return None
    try: return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError: return None


def _parse_highlight_flag(raw_value: Optional[str]) -> bool:
    return (raw_value or "").strip().lower() in _HIGHLIGHT_TRUE_VALUES


def _build_preview_highlights(document: Document) -> list[str]:
    highlights: list[str] = []

    def _push(value: Optional[str]) -> None:
        cleaned = (value or "").strip()
        if cleaned and cleaned not in highlights:
            highlights.append(cleaned)

    supplier_name = document.supplier.name if document.supplier else ""
    _push(supplier_name)
    _push(document.document_number or "")

    if document.total_gross_amount is not None:
        _push(format_amount(document.total_gross_amount, use_grouping=True))
        _push(format_amount(document.total_gross_amount, use_grouping=False))
        _push(str(document.total_gross_amount))

    return highlights


def _inject_preview_highlights(html_content: str, highlights: list[str]) -> str:
    if not highlights:
        return html_content

    payload = json.dumps({"values": highlights}, ensure_ascii=False)
    injection = f"""
<style>
.preview-highlight {{
    background: #fff3b0;
    border-radius: 2px;
    box-shadow: inset 0 0 0 1px #f2c94c;
    padding: 0 2px;
}}
</style>
<script id="preview-highlight-data" type="application/json">{payload}</script>
<script>
(() => {{
    const dataEl = document.getElementById("preview-highlight-data");
    if (!dataEl) return;
    let values = [];
    try {{
        const data = JSON.parse(dataEl.textContent || "{{}}");
        values = Array.isArray(data.values) ? data.values : [];
    }} catch (err) {{
        return;
    }}

    values = values
        .map((val) => String(val || "").trim())
        .filter((val) => val.length > 0)
        .sort((a, b) => b.length - a.length);
    if (!values.length) return;

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {{
        acceptNode: (node) => {{
            if (!node || !node.parentNode) return NodeFilter.FILTER_REJECT;
            const parent = node.parentNode;
            const tag = parent.nodeName ? parent.nodeName.toLowerCase() : "";
            if (tag === "script" || tag === "style") return NodeFilter.FILTER_REJECT;
            if (parent.classList && parent.classList.contains("preview-highlight")) {{
                return NodeFilter.FILTER_REJECT;
            }}
            return NodeFilter.FILTER_ACCEPT;
        }},
    }});

    const nodes = [];
    while (walker.nextNode()) {{
        nodes.push(walker.currentNode);
    }}

    const applyHighlights = (text) => {{
        const parts = [];
        let index = 0;

        while (index < text.length) {{
            let matchIndex = -1;
            let matchValue = "";
            for (const value of values) {{
                const found = text.indexOf(value, index);
                if (found !== -1 && (matchIndex === -1 || found < matchIndex)) {{
                    matchIndex = found;
                    matchValue = value;
                }}
            }}
            if (matchIndex === -1) {{
                parts.push(document.createTextNode(text.slice(index)));
                break;
            }}
            if (matchIndex > index) {{
                parts.push(document.createTextNode(text.slice(index, matchIndex)));
            }}
            const span = document.createElement("span");
            span.className = "preview-highlight";
            span.textContent = matchValue;
            parts.push(span);
            index = matchIndex + matchValue.length;
        }}

        return parts;
    }};

    nodes.forEach((node) => {{
        const text = node.nodeValue || "";
        if (!text) return;
        const parts = applyHighlights(text);
        if (
            parts.length === 1 &&
            parts[0].nodeType === Node.TEXT_NODE &&
            parts[0].nodeValue === text
        ) {{
            return;
        }}
        const frag = document.createDocumentFragment();
        parts.forEach((part) => frag.appendChild(part));
        node.parentNode.replaceChild(frag, node);
    }});
}})();
</script>
"""

    lowered = html_content.lower()
    insert_at = lowered.rfind("</body>")
    if insert_at == -1:
        insert_at = lowered.rfind("</html>")
    if insert_at == -1:
        return html_content + injection
    return html_content[:insert_at] + injection + html_content[insert_at:]


@documents_bp.route("/", methods=["GET"])
def list_view():
    filters = DocumentSearchFilters.from_query_args(request.args)
    sort_field = request.args.get("sort") or None
    sort_dir = request.args.get("dir") or "desc"

    has_query_args = bool(request.args)
    documents = []
    if has_query_args:
        documents = doc_service.search_documents(filters=filters, limit=300, document_type=None)
        if sort_field in {"date", "number", "amount"}:
            reverse = (sort_dir == "desc")
            if sort_field == "date":
                documents = sorted(
                    documents,
                    key=lambda d: d.document_date or date.min,
                    reverse=reverse,
                )
            elif sort_field == "number":
                documents = sorted(
                    documents,
                    key=lambda d: (d.document_number or "").lower(),
                    reverse=reverse,
                )
            elif sort_field == "amount":
                documents = sorted(
                    documents,
                    key=lambda d: d.total_gross_amount or 0,
                    reverse=reverse,
                )
        else:
            # Ordinamento di default: da rivedere -> verificati non pagati -> pagati/archiviati
            status_priority = {
                "pending_physical_copy": 0,
                "verified": 1,
                "archived": 2,
            }
            documents = sorted(
                documents,
                key=lambda d: (
                    status_priority.get(d.doc_status, 5),
                    0 if not getattr(d, "is_paid", False) else 1,
                    -(d.document_date.toordinal() if d.document_date else date.min.toordinal()),
                    -d.id,
                ),
            )

    suppliers = list_active_suppliers()
    legal_entities = list_legal_entities(include_inactive=False)
    
    # FIX: Chiamata al service invece che al repo
    accounting_years = doc_service.get_accounting_years()
    query_args = request.args.to_dict()
    base_query_args = {k: v for k, v in query_args.items() if k not in {"sort", "dir"}}
    date_dir = "asc" if sort_field != "date" or sort_dir == "desc" else "desc"
    number_dir = "asc" if sort_field != "number" or sort_dir == "desc" else "desc"
    amount_dir = "asc" if sort_field != "amount" or sort_dir == "desc" else "desc"
    date_url = url_for("documents.list_view", **base_query_args, sort="date", dir=date_dir)
    number_url = url_for("documents.list_view", **base_query_args, sort="number", dir=number_dir)
    amount_url = url_for("documents.list_view", **base_query_args, sort="amount", dir=amount_dir)

    today = date.today()
    preset_links = {
        "last_7": url_for(
            "documents.list_view",
            date_from=(today - timedelta(days=7)).isoformat(),
            date_to=today.isoformat(),
        ),
        "last_30": url_for(
            "documents.list_view",
            date_from=(today - timedelta(days=30)).isoformat(),
            date_to=today.isoformat(),
        ),
        "review": url_for("documents.list_view", doc_status="pending_physical_copy"),
    }

    supplier_lookup = {supplier.id: supplier.name for supplier in suppliers}
    legal_entity_lookup = {entity.id: entity.name for entity in legal_entities}

    def _fmt_date(value: Optional[date]) -> str:
        if not value:
            return "-"
        return value.strftime("%d/%m/%Y")

    active_filter_chips = []

    def _add_chip(label: str, keys: list[str]) -> None:
        next_args = dict(query_args)
        for key in keys:
            next_args.pop(key, None)
        active_filter_chips.append(
            {
                "label": label,
                "remove_url": url_for("documents.list_view", **next_args),
            }
        )

    if filters.q:
        _add_chip(f"Cerca: {filters.q}", ["q"])
    if filters.document_number:
        _add_chip(f"Numero: {filters.document_number}", ["document_number"])
    if filters.document_type:
        type_labels = {
            "invoice": "Fatture",
            "credit_note": "Note di credito",
            "f24": "F24",
            "insurance": "Assicurazioni",
            "mav": "MAV",
            "cbill": "CBILL",
            "receipt": "Scontrini",
            "rent": "Affitti",
            "tax": "Tributi",
            "other": "Altro",
        }
        label = type_labels.get(filters.document_type, filters.document_type)
        _add_chip(f"Tipo: {label}", ["document_type", "type"])
    if filters.date_from or filters.date_to:
        _add_chip(
            f"Data: {_fmt_date(filters.date_from)} - {_fmt_date(filters.date_to)}",
            ["date_from", "date_to"],
        )
    if filters.accounting_year:
        year_key = "accounting_year" if "accounting_year" in query_args else "year"
        _add_chip(f"Anno: {filters.accounting_year}", [year_key])
    if filters.supplier_id:
        supplier_name = supplier_lookup.get(filters.supplier_id, f"ID {filters.supplier_id}")
        _add_chip(f"Fornitore: {supplier_name}", ["supplier_id"])
    if filters.legal_entity_id:
        entity_name = legal_entity_lookup.get(filters.legal_entity_id, f"ID {filters.legal_entity_id}")
        _add_chip(f"Intestatario: {entity_name}", ["legal_entity_id"])
    if filters.category_id:
        _add_chip(f"Categoria: ID {filters.category_id}", ["category_id"])
    if filters.category_unassigned:
        _add_chip("Senza categoria", ["category_unassigned"])
    if filters.doc_status:
        status_labels = {
            "pending_physical_copy": "Da rivedere",
            "verified": "Verificato",
            "archived": "Archiviato",
        }
        _add_chip(f"Stato: {status_labels.get(filters.doc_status, filters.doc_status)}", ["doc_status"])
    if filters.payment_status:
        payment_labels = {
            "unpaid": "Non pagato",
            "partial": "Parziale",
            "paid": "Pagato",
        }
        _add_chip(f"Pagamento: {payment_labels.get(filters.payment_status, filters.payment_status)}", ["payment_status"])
    if filters.physical_copy_status:
        physical_labels = {
            "missing": "Mancante",
            "requested": "Richiesta",
            "received": "Ricevuta",
        }
        _add_chip(
            f"Copia fisica: {physical_labels.get(filters.physical_copy_status, filters.physical_copy_status)}",
            ["physical_copy_status"],
        )
    if filters.amount_value is not None:
        operator_label = "<" if filters.amount_operator == "lt" else ">"
        amount_value = format_amount(filters.amount_value)
        _add_chip(
            f"Importo {operator_label} {amount_value}",
            ["amount_value", "amount_operator", "min_total", "max_total"],
        )
    elif filters.min_total is not None or filters.max_total is not None:
        min_label = format_amount(filters.min_total) if filters.min_total is not None else "-"
        max_label = format_amount(filters.max_total) if filters.max_total is not None else "-"
        _add_chip(
            f"Importo: {min_label} - {max_label}",
            ["min_total", "max_total", "amount_value", "amount_operator"],
        )

    has_active_filters = len(active_filter_chips) > 0
    has_advanced_filters = any(
        [
            filters.document_number,
            filters.document_type,
            filters.date_from,
            filters.date_to,
            filters.supplier_id,
            filters.legal_entity_id,
            filters.accounting_year,
            filters.category_id,
            filters.category_unassigned,
            filters.doc_status,
            filters.payment_status,
            filters.physical_copy_status,
            filters.amount_value is not None,
            filters.min_total is not None,
            filters.max_total is not None,
        ]
    )

    return render_template(
        "documents/list.html",
        documents=documents,
        suppliers=suppliers,
        legal_entities=legal_entities,
        accounting_years=accounting_years,
        filters=filters,
        sort_field=sort_field,
        sort_dir=sort_dir,
        base_query_args=base_query_args,
        date_url=date_url,
        number_url=number_url,
        amount_url=amount_url,
        preset_links=preset_links,
        has_query_args=has_query_args,
        has_active_filters=has_active_filters,
        has_advanced_filters=has_advanced_filters,
        active_filter_chips=active_filter_chips,
    )


@documents_bp.route("/new", methods=["GET", "POST"])
def manual_create_view():
    suppliers = list_active_suppliers()
    legal_entities = list_legal_entities(include_inactive=False)
    form_data: dict = {}

    if request.method == "POST":
        form_data = request.form.to_dict()
        file = request.files.get("document_pdf")
        ok, message, doc_id = doc_service.create_manual_document(form_data)
        if ok and doc_id:
            if file is not None and file.filename:
                if not _is_allowed_file(file.filename):
                    flash("Formato file non supportato per il PDF.", "warning")
                else:
                    try:
                        doc_service.mark_physical_copy_received(doc_id, file=file)
                    except Exception as exc:
                        flash(f"Errore durante il salvataggio del PDF: {exc}", "warning")
            flash(message, "success")
            return redirect(url_for("documents.detail_view", document_id=doc_id))
        flash(message, "danger")

    return render_template(
        "documents/manual_create.html",
        suppliers=suppliers,
        legal_entities=legal_entities,
        form_data=form_data,
    )

@documents_bp.route("/review/list", methods=["GET"])
def review_list_view():
    order = request.args.get("order", "desc")
    raw_legal_entity_id = request.args.get("legal_entity_id") or None
    legal_entity_id = None
    if raw_legal_entity_id:
        try:
            legal_entity_id = int(raw_legal_entity_id)
        except ValueError:
            legal_entity_id = None

    documents = doc_service.list_documents_to_review(
        order=order,
        document_type=None,
        legal_entity_id=legal_entity_id,
    )
    next_doc = doc_service.get_next_document_to_review(
        order=order,
        document_type=None,
        legal_entity_id=legal_entity_id,
    )
    from app.repositories.legal_entity_repo import list_legal_entities
    legal_entities = list_legal_entities(include_inactive=False)
    le_counts = doc_service.count_documents_to_review_by_legal_entity()

    return render_template(
        "documents/review_list.html",
        invoices=documents, 
        next_invoice=next_doc,
        legal_entities=legal_entities,
        selected_legal_entity_id=legal_entity_id,
        le_counts=le_counts,
        order=order,
    )

@documents_bp.route("/review", methods=["GET"])
def review_loop_redirect_view():
    next_doc = doc_service.get_next_document_to_review(document_type=None)
    if next_doc:
        return redirect(url_for("documents.review_loop_invoice_view", document_id=next_doc.id))
    flash("Tutti i documenti importati sono stati gestiti.", "success")
    return redirect(url_for("documents.list_view"))

@documents_bp.route("/review/<int:document_id>", methods=["GET", "POST"])
def review_loop_invoice_view(document_id: int):
    if request.method == "POST":
        action = request.form.get("action") or "review"
        if action == "review":
            success, message = DocumentService.review_and_confirm(document_id, request.form.to_dict())
            if not success:
                if message == "Documento non trovato": abort(404)
                flash(message, "danger")
            else:
                flash("Documento confermato e passato al successivo.", "success")
                return redirect(url_for("documents.review_loop_redirect_view"))
        elif action == "match_ddt":
            delivery_note_id = request.form.get("delivery_note_id")
            status = request.form.get("ddt_status") or "matched"
            if not delivery_note_id:
                flash("Seleziona un DDT da abbinare.", "warning")
            else:
                try:
                    link_delivery_note_to_document(int(delivery_note_id), document_id, status=status)
                    flash("DDT abbinato con successo.", "success")
                except Exception as exc:
                    flash(f"Errore in abbinamento DDT: {exc}", "danger")
        elif action == "upload_physical_copy":
            file = request.files.get("physical_copy_file")
            if file is None or not file.filename:
                flash("Seleziona un file PDF da caricare.", "warning")
            else:
                doc = doc_service.mark_physical_copy_received(document_id, file=file)
                if doc is None:
                    flash("Documento non trovato.", "warning")
                else:
                    flash("Copia fisica caricata e collegata.", "success")

    document = DocumentService.get_document_by_id(document_id)
    if document is None: abort(404)
    from app.services.settings_service import get_setting
    default_xsl = get_setting("DEFAULT_XSL_STYLE", "asso")

    # DDT candidati e collegati
    ddt_candidates = []
    if document.supplier_id:
        ddt_candidates = find_delivery_note_candidates(
            supplier_id=document.supplier_id,
            ddt_number=request.args.get("ddt_number") or None,
            ddt_date=None,  # lasciamo filtro data libero per ora
            allowed_statuses=["unmatched", "linked"],
            limit=200,
            exclude_document_ids=[document_id],
        )
    linked_ddt = list_delivery_notes_by_document(document_id) if document else []
    legal_entities = list_legal_entities(include_inactive=False)
    return render_template(
        'documents/review.html',
        invoice=document,
        today=date.today(),
        default_xsl=default_xsl,
        ddt_candidates=ddt_candidates,
        linked_ddt=linked_ddt,
        legal_entities=legal_entities,
    )

@documents_bp.route("/review/<int:document_id>/delete", methods=["POST"])
def delete_document(document_id: int):
    ok = DocumentService.delete_document(document_id)
    if not ok:
        abort(404)
    flash("Documento scartato ed eliminato. Potrai reimportarlo.", "info")
    return redirect(url_for("documents.review_loop_redirect_view"))

    
def _resolve_document_xml_path(document):
    from app.services.settings_service import get_xml_storage_path
    xml_storage = get_xml_storage_path()
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "storage/uploads")
    xml_full_path = None

    if document.file_path:
        if os.path.isabs(document.file_path):
             xml_full_path = document.file_path
        else:
             xml_full_path = os.path.join(xml_storage, document.file_path)
             if not os.path.exists(xml_full_path):
                 legacy_path = os.path.join(upload_folder, document.file_path)
                 if os.path.exists(legacy_path):
                     xml_full_path = legacy_path

    elif document.import_source:
        candidate_path = document.import_source
        if candidate_path.lower().endswith(('.xml', '.p7m', '.xml.p7m')):
            xml_full_path = candidate_path
        elif document.file_name:
            xml_full_path = os.path.join(candidate_path, document.file_name)
        else:
            xml_full_path = candidate_path

    return xml_full_path


def _find_wkhtmltopdf_bin():
    env_bin = os.environ.get("WKHTMLTOPDF_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin
    bin_path = shutil.which("wkhtmltopdf")
    if bin_path:
        return bin_path
    candidates = [
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _render_pdf_from_html(html_content: str, base_dir: str, logger):
    wkhtmltopdf_bin = _find_wkhtmltopdf_bin()
    if wkhtmltopdf_bin:
        html_path = None
        pdf_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as html_file:
                html_file.write(html_content)
                html_path = html_file.name
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_file:
                pdf_path = pdf_file.name
            result = subprocess.run(
                [wkhtmltopdf_bin, "--encoding", "utf-8", html_path, pdf_path],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, "rb") as handle:
                    return handle.read()
            if logger:
                logger.warning(
                    "wkhtmltopdf fallito",
                    extra={
                        "component": "documents",
                        "stderr": (result.stderr or "").strip(),
                        "stdout": (result.stdout or "").strip(),
                    },
                )
        finally:
            if html_path and os.path.exists(html_path):
                os.unlink(html_path)
            if pdf_path and os.path.exists(pdf_path):
                os.unlink(pdf_path)

    try:
        from weasyprint import HTML  # type: ignore
    except Exception:
        return None
    try:
        return HTML(string=html_content, base_url=base_dir).write_pdf()
    except Exception as exc:
        if logger:
            logger.warning(
                "WeasyPrint fallito",
                extra={"component": "documents", "error": str(exc)},
            )
        return None


def _build_pdf_download_name(document_id: int, file_name: Optional[str]) -> str:
    base_name = file_name or f"document_{document_id}"
    lowered = base_name.lower()
    if lowered.endswith(".xml.p7m"):
        base_name = base_name[:-len(".xml.p7m")]
    elif lowered.endswith(".p7m"):
        base_name = base_name[:-len(".p7m")]
    elif lowered.endswith(".xml"):
        base_name = base_name[:-len(".xml")]
    return f"{base_name}.pdf"


@documents_bp.route("/preview/<int:document_id>", methods=["GET"], endpoint="preview_visual")
def preview_visual(document_id: int):
    document = DocumentService.get_document_by_id(document_id)
    if document is None:
        abort(404)

    xml_full_path = _resolve_document_xml_path(document)
    if not xml_full_path:
        return "<h1>Errore</h1><p>Nessun percorso file presente nel database.</p>", 404

    # Seleziona XSL da querystring (fogli di stile AE)
    # Tre opzioni esposte: Asso (custom), Ordinaria (AE) e Semplificata VFSM10 (AE)
    style_map = {
        "asso": "FoglioStileAssoSoftware.xsl",
        # scegliamo l'ordinaria come foglio AE predefinito
        "ordinaria": "Foglio_di_stile_fattura_ordinaria_ver1.2.3.xsl",
        "vfsm10": "Foglio_di_stile_VFSM10_v1.0.2.xsl",
    }
    style_key = request.args.get("style", "asso")
    xsl_name = style_map.get(style_key, style_map["ordinaria"])
    # resources/ vive alla radice del progetto (un livello sopra current_app.root_path)
    base_dir = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    xsl_full_path = os.path.join(base_dir, "resources", "xsl", xsl_name)

    try:
        html_content = render_invoice_html(xml_full_path, xsl_full_path)
        if _parse_highlight_flag(request.args.get("highlight")):
            highlights = _build_preview_highlights(document)
            html_content = _inject_preview_highlights(html_content, highlights)
        return render_template_string(html_content)
    except FileNotFoundError:
        return f"<h1>File non trovato</h1><p>Il sistema ha cercato qui:<br><code>{xml_full_path}</code><br>Ma il file non esiste.</p>", 404
    except Exception as e:
        return f"<h1>Errore di visualizzazione</h1><p>{str(e)}</p>", 500


@documents_bp.route("/download/<int:document_id>", methods=["GET"], endpoint="download_source")
def download_source(document_id: int):
    document = DocumentService.get_document_by_id(document_id)
    if document is None:
        abort(404)

    xml_full_path = _resolve_document_xml_path(document)
    if not xml_full_path:
        return "<h1>Errore</h1><p>Nessun percorso file presente nel database.</p>", 404
    if not os.path.exists(xml_full_path):
        return f"<h1>File non trovato</h1><p>Il sistema ha cercato qui:<br><code>{xml_full_path}</code><br>Ma il file non esiste.</p>", 404

    download_name = document.file_name or os.path.basename(xml_full_path) or f"document_{document_id}.xml"
    lower_name = download_name.lower()
    if lower_name.endswith(".p7m") or lower_name.endswith(".xml.p7m"):
        mimetype = "application/pkcs7-mime"
    else:
        mimetype = "application/xml"
    return send_file(xml_full_path, mimetype=mimetype, as_attachment=True, download_name=download_name)


@documents_bp.route("/pdf/<int:document_id>", methods=["GET"], endpoint="download_pdf")
def download_pdf(document_id: int):
    document = DocumentService.get_document_by_id(document_id)
    if document is None:
        abort(404)

    xml_full_path = _resolve_document_xml_path(document)
    if not xml_full_path:
        return "<h1>Errore</h1><p>Nessun percorso file presente nel database.</p>", 404
    if not os.path.exists(xml_full_path):
        return f"<h1>File non trovato</h1><p>Il sistema ha cercato qui:<br><code>{xml_full_path}</code><br>Ma il file non esiste.</p>", 404

    style_map = {
        "asso": "FoglioStileAssoSoftware.xsl",
        "ordinaria": "Foglio_di_stile_fattura_ordinaria_ver1.2.3.xsl",
        "vfsm10": "Foglio_di_stile_VFSM10_v1.0.2.xsl",
    }
    style_key = request.args.get("style", "asso")
    xsl_name = style_map.get(style_key, style_map["ordinaria"])
    base_dir = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    xsl_full_path = os.path.join(base_dir, "resources", "xsl", xsl_name)

    try:
        html_content = render_invoice_html(xml_full_path, xsl_full_path)
    except Exception as exc:
        return f"<h1>Errore generazione HTML</h1><p>{str(exc)}</p>", 500

    pdf_bytes = _render_pdf_from_html(html_content, base_dir, current_app.logger)
    if not pdf_bytes:
        return (
            "<h1>PDF non disponibile</h1>"
            "<p>Installa wkhtmltopdf o weasyprint per abilitare la conversione.</p>",
            501,
        )

    download_name = _build_pdf_download_name(document_id, document.file_name)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=download_name,
    )


@documents_bp.route("/ocr-map", methods=["POST"])
def ocr_map_view():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"success": False, "error": "File mancante."}), 400

    suffix = Path(file.filename).suffix.lower()
    if not suffix:
        return jsonify({"success": False, "error": "Estensione file mancante."}), 400

    from app.services.settings_service import get_setting
    default_lang = get_setting("OCR_DEFAULT_LANG", "ita")
    lang = (request.form.get("lang") or default_lang).strip() or default_lang
    max_pages = ocr_service.normalize_max_pages(
        request.form.get("max_pages"),
        default=int(get_setting("OCR_MAX_PAGES", "5") or 5),
    )

    try:
        text = ocr_service.extract_text_from_bytes(
            file.read(),
            suffix=suffix,
            lang=lang,
            max_pages=max_pages,
            logger=current_app.logger,
        )
    except ocr_service.OcrDependencyError as exc:
        return jsonify({"success": False, "error": f"OCR non disponibile: {exc}"}), 400
    except ocr_service.OcrError as exc:
        return jsonify({"success": False, "error": f"OCR fallito: {exc}"}), 400

    text = (text or "").strip()
    if not text:
        return jsonify({"success": False, "error": "OCR completato ma nessun testo estratto."}), 200

    fields = parse_manual_document_fields(text)
    return jsonify({"success": True, "text": text, "fields": fields})

@documents_bp.route("/<int:document_id>", methods=["GET"])
def detail_view(document_id: int):
    detail = doc_service.get_document_detail(document_id)
    if detail is None:
        flash("Documento non trovato.", "warning")
        return redirect(url_for("documents.list_view"))

    from app.services.settings_service import get_setting
    detail["default_xsl"] = get_setting("DEFAULT_XSL_STYLE", "asso")

    # DDT collegati a questa fattura (match manuale)
    from app.services.delivery_note_service import (
        list_delivery_notes_by_document,
    )
    detail["linked_delivery_notes"] = list_delivery_notes_by_document(document_id)
    payments = detail.get("payments") or []
    paid_total = sum(float(p.paid_amount or 0) for p in payments)
    gross_total = float(detail["invoice"].total_gross_amount or 0)
    remaining_amount = gross_total - paid_total
    if remaining_amount < 0:
        remaining_amount = 0.0
    detail["remaining_amount"] = remaining_amount

    return render_template("documents/detail.html", **detail)


@documents_bp.route("/<int:document_id>/match-ddt", methods=["GET", "POST"])
def match_delivery_notes_view(document_id: int):
    invoice = DocumentService.get_document_by_id(document_id)
    if invoice is None:
        flash("Documento non trovato.", "warning")
        return redirect(url_for("documents.list_view"))

    if request.method == "POST":
        delivery_note_id = request.form.get("delivery_note_id")
        status = request.form.get("status") or "matched"
        if not delivery_note_id:
            flash("Seleziona un DDT.", "warning")
            return redirect(url_for("documents.match_delivery_notes_view", document_id=document_id))
        try:
            link_delivery_note_to_document(int(delivery_note_id), document_id, status=status)
            flash("DDT abbinato con successo.", "success")
        except Exception as exc:
            flash(f"Errore in abbinamento: {exc}", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))

    supplier_id = invoice.supplier_id
    candidates = []
    if supplier_id:
        candidates = find_delivery_note_candidates(
            supplier_id=supplier_id,
            allowed_statuses=["unmatched", "linked"],
            limit=200,
        )

    return render_template(
        "documents/match_delivery_notes.html",
        invoice=invoice,
        candidates=candidates,
    )

@documents_bp.route("/<int:document_id>/status", methods=["POST"])
def update_status_view(document_id: int):
    allowed_doc_statuses = {"pending_physical_copy", "verified", "archived"}
    doc_status = request.form.get("doc_status") or None
    
    if doc_status is not None and doc_status not in allowed_doc_statuses:
        flash("Valore di stato documento non valido.", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))
    
    due_date_str = request.form.get("due_date") or ""
    due_date = _parse_date(due_date_str)
    note = request.form.get("note")

    doc = doc_service.update_document_status(document_id=document_id, doc_status=doc_status, due_date=due_date, note=note)
    if doc is None:
        flash("Documento non trovato.", "danger")
    else:
        flash("Stato aggiornato con successo.", "success")

    next_url = request.form.get("next") or request.args.get("next")
    if next_url and _is_safe_next(next_url):
        return redirect(next_url)
    return redirect(url_for("documents.detail_view", document_id=document_id))


def _is_safe_next(target: str) -> bool:
    parsed = urlparse(target)
    return parsed.scheme == "" and parsed.netloc == ""

@documents_bp.route("/<int:document_id>/physical-copy/upload", methods=["POST"], endpoint="upload_physical_copy")
def upload_physical_copy_view(document_id: int):
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Seleziona un file da caricare.", "warning")
        return redirect(url_for("documents.detail_view", document_id=document_id))
    if not _is_allowed_file(file.filename):
        flash("Formato file non supportato.", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))

    doc = doc_service.mark_physical_copy_received(document_id, file=file)
    if doc is None: abort(404)
    flash("Copia fisica caricata.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))

@documents_bp.route("/<int:document_id>/physical-copy/request", methods=["POST"], endpoint="request_physical_copy")
def request_physical_copy_view(document_id: int):
    invoice = doc_service.request_physical_copy(document_id)
    if invoice is None: abort(404)
    flash("Richiesta copia fisica registrata.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))

@documents_bp.route("/<int:document_id>/physical-copy/received", methods=["POST"], endpoint="mark_physical_copy_received")
def mark_physical_copy_received_view(document_id: int):
    invoice = doc_service.mark_physical_copy_received(document_id, file=None)
    if invoice is None: abort(404)
    flash("Copia fisica segnata come ricevuta.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))

@documents_bp.route("/<int:document_id>/confirm", methods=["POST"])
def confirm_invoice(document_id: int):
    order = request.args.get("order", "desc")
    invoice = doc_service.confirm_document(document_id)
    if invoice is None: abort(404)
    flash("Documento confermato.", "success")
    next_invoice = doc_service.get_next_document_to_review(order=order, document_type=None)
    if next_invoice:
        return redirect(url_for("documents.detail_view", document_id=next_invoice.id, order=order))
    flash("Nessun altro documento da rivedere.", "info")
    return redirect(url_for("documents.review_list_view", order=order))

@documents_bp.route("/<int:document_id>/reject", methods=["POST"])
def reject_invoice(document_id: int):
    order = request.args.get("order", "desc")
    invoice = doc_service.reject_document(document_id)
    if invoice is None: abort(404)
    flash("Documento archiviato.", "success")
    next_invoice = doc_service.get_next_document_to_review(order=order, document_type=None)
    if next_invoice:
        return redirect(url_for("documents.detail_view", document_id=next_invoice.id, order=order))
    flash("Nessun altro documento da rivedere.", "info")
    return redirect(url_for("documents.review_list_view", order=order))

@documents_bp.get("/<int:document_id>/attach-scan")
def attach_scan_view(document_id: int):
    document = Document.query.get_or_404(document_id)
    return render_template("documents/attach_scan.html", invoice=document)

@documents_bp.post("/<int:document_id>/attach-scan")
def attach_scan_process(document_id: int):
    document = Document.query.get_or_404(document_id)
    
    file = request.files.get("file")
    if file is None or not file.filename:
        flash("Seleziona un file da caricare.", "warning")
        return redirect(url_for("documents.attach_scan_view", document_id=document_id))

    if not _is_allowed_file(file.filename):
        flash("Formato file non supportato (usa PDF, JPG, PNG).", "danger")
        return redirect(url_for("documents.attach_scan_view", document_id=document_id))

    doc_service.mark_physical_copy_received(document_id, file=file)
    
    flash("Scansione caricata e collegata correttamente.", "success")
    return redirect(url_for("documents.detail_view", document_id=document_id))

@documents_bp.route("/<int:document_id>/physical-copy/view", methods=["GET"])
def view_physical_copy(document_id: int):
    document = Document.query.get_or_404(document_id)
    
    if not document.physical_copy_file_path:
        abort(404)

    from app.services.settings_service import get_physical_copy_storage_path
    base_path = get_physical_copy_storage_path()
    
    full_path = os.path.join(base_path, document.physical_copy_file_path)
    
    if not os.path.exists(full_path):
        flash("File fisico non trovato sul disco.", "danger")
        return redirect(url_for("documents.detail_view", document_id=document_id))

    return send_file(full_path, as_attachment=False)

@documents_bp.route("/<int:document_id>/physical-copy/remove", methods=["POST"])
def remove_physical_copy(document_id: int):
    document = Document.query.get_or_404(document_id)
    
    if not document.physical_copy_file_path:
        flash("Nessuna copia fisica da rimuovere.", "warning")
        return redirect(url_for("documents.detail_view", document_id=document_id))

    from app.extensions import db
    
    previous_path = document.physical_copy_file_path
    document.physical_copy_file_path = None
    document.physical_copy_status = "missing" 
    document.physical_copy_received_at = None
    
    db.session.add(document)
    db.session.commit()
    
    flash(f"Collegamento rimosso. (Il file {os.path.basename(previous_path)} è rimasto in archivio)", "info")
    return redirect(url_for("documents.detail_view", document_id=document_id))
