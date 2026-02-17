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


def render_pdf_from_html(html_content: str, base_dir: str, logger) -> Optional[bytes]:
    wkhtmltopdf_bin = find_wkhtmltopdf_bin()
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
        return HTML(string=html_content, base_url=base_dir).write_pdf()
    except Exception as exc:
        if logger:
            logger.warning(
                "WeasyPrint fallito",
                extra={"component": "pdf", "error": str(exc)},
            )
        return None
