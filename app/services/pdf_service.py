"""
Utility per la generazione di PDF da HTML.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Optional


def find_wkhtmltopdf_bin() -> Optional[str]:
    env_bin = os.environ.get("WKHTMLTOPDF_BIN")
    if env_bin and os.path.isfile(env_bin):
        return env_bin
    bin_path = shutil.which("wkhtmltopdf")
    if bin_path:
        return bin_path
    for candidate in (
        r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
        r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def _prepare_html_for_pdf(
    html_content: str,
    *,
    page_size: str,
    orientation: str,
) -> str:
    page_rule = f"{page_size} {'landscape' if orientation.lower() == 'landscape' else 'portrait'}"
    injection = f"""
<style id="pdf-render-normalize">
@page {{
    size: {page_rule};
    margin: 10mm;
}}
html, body {{
    max-width: 100% !important;
    overflow: visible !important;
}}
img, svg, canvas {{
    max-width: 100% !important;
    height: auto !important;
}}
table {{
    max-width: 100% !important;
}}
</style>
"""
    lowered = html_content.lower()
    if 'id="pdf-render-normalize"' in lowered:
        return html_content
    if "</head>" in lowered:
        idx = lowered.rfind("</head>")
        return html_content[:idx] + injection + html_content[idx:]
    return f"<html><head>{injection}</head><body>{html_content}</body></html>"


def render_pdf_from_html(
    html_content: str,
    base_dir: str,
    logger,
    *,
    page_size: str = "A4",
    orientation: str = "Portrait",
) -> Optional[bytes]:
    prepared_html = _prepare_html_for_pdf(
        html_content,
        page_size=page_size,
        orientation=orientation,
    )
    wkhtmltopdf_bin = find_wkhtmltopdf_bin()
    if wkhtmltopdf_bin:
        html_path = None
        pdf_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as html_file:
                html_file.write(prepared_html)
                html_path = html_file.name
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as pdf_file:
                pdf_path = pdf_file.name
            result = subprocess.run(
                [
                    wkhtmltopdf_bin,
                    "--encoding", "utf-8",
                    "--enable-local-file-access",
                    "--print-media-type",
                    "--page-size", page_size,
                    "--orientation", orientation,
                    "--margin-top", "10mm",
                    "--margin-right", "10mm",
                    "--margin-bottom", "10mm",
                    "--margin-left", "10mm",
                    "--viewport-size", "1400x1980",
                    html_path,
                    pdf_path,
                ],
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
                        "component": "pdf",
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
        return HTML(string=prepared_html, base_url=base_dir).write_pdf()
    except Exception as exc:
        if logger:
            logger.warning(
                "WeasyPrint fallito",
                extra={"component": "pdf", "error": str(exc)},
            )
        return None
