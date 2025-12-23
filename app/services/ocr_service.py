"""
OCR helper per estrarre testo da PDF e immagini.
Dipendenze opzionali: pytesseract, Pillow, pdf2image, pypdf.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional


class OcrError(Exception):
    """Errore generico OCR."""


class OcrDependencyError(OcrError):
    """Dipendenze OCR mancanti o non configurate."""


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf"}


def normalize_max_pages(value: str | None, default: int = 5, max_limit: int = 12) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    if parsed < 1:
        return default
    return min(parsed, max_limit)


def extract_text_from_bytes(
    data: bytes,
    *,
    suffix: str,
    lang: str = "ita",
    max_pages: int = 5,
    logger: Optional[object] = None,
) -> str:
    normalized = (suffix or "").lower()
    if normalized and not normalized.startswith("."):
        normalized = f".{normalized}"
    if not normalized or normalized not in SUPPORTED_EXTENSIONS:
        raise OcrError(f"Formato file non supportato: {normalized or 'sconosciuto'}")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=normalized) as tmp:
            tmp.write(data)
            tmp.flush()
            tmp_path = tmp.name
        return extract_text(
            tmp_path,
            lang=lang,
            max_pages=max_pages,
            logger=logger,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def extract_text(
    file_path: str | Path,
    *,
    lang: str = "ita",
    max_pages: int = 5,
    logger: Optional[object] = None,
) -> str:
    path = Path(file_path)
    if not path.is_file():
        raise OcrError(f"File non trovato: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text_layer(path, max_pages=max_pages)
        if text and len(text.strip()) >= 80:
            return text
        if logger:
            logger.info(
                "PDF text layer empty, fallback to OCR",
                extra={"file": str(path), "pages": max_pages},
            )
        return _ocr_pdf_images(path, lang=lang, max_pages=max_pages)
    if suffix in IMAGE_EXTENSIONS:
        return _ocr_image(path, lang=lang)

    raise OcrError(f"Formato file non supportato: {suffix}")


def _extract_pdf_text_layer(path: Path, *, max_pages: int) -> str:
    try:
        from pypdf import PdfReader
    except Exception:
        return ""

    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""

    chunks: list[str] = []
    for idx, page in enumerate(reader.pages):
        if idx >= max_pages:
            break
        try:
            chunk = page.extract_text() or ""
        except Exception:
            chunk = ""
        if chunk:
            chunks.append(chunk)
    return "\n".join(chunks).strip()


def _ocr_pdf_images(path: Path, *, lang: str, max_pages: int) -> str:
    pytesseract = _get_pytesseract()
    convert_from_path = _get_pdf2image()

    poppler_path = os.environ.get("POPPLER_PATH") or None
    images = convert_from_path(
        str(path),
        dpi=300,
        first_page=1,
        last_page=max_pages,
        poppler_path=poppler_path,
    )
    chunks: list[str] = []
    for img in images:
        try:
            text = pytesseract.image_to_string(img, lang=lang)
        except Exception as exc:
            raise OcrError(f"OCR fallito su pagina: {exc}") from exc
        if text:
            chunks.append(text)
    return "\n".join(chunks).strip()


def _ocr_image(path: Path, *, lang: str) -> str:
    pytesseract = _get_pytesseract()
    try:
        from PIL import Image
    except Exception as exc:
        raise OcrDependencyError("Pillow non installato") from exc

    try:
        img = Image.open(path)
    except Exception as exc:
        raise OcrError(f"Immagine non leggibile: {exc}") from exc

    try:
        return (pytesseract.image_to_string(img, lang=lang) or "").strip()
    except Exception as exc:
        raise OcrError(f"OCR fallito su immagine: {exc}") from exc


def _get_pytesseract():
    try:
        import pytesseract
    except Exception as exc:
        raise OcrDependencyError("pytesseract non installato") from exc

    tess_cmd = os.environ.get("TESSERACT_CMD")
    if tess_cmd:
        pytesseract.pytesseract.tesseract_cmd = tess_cmd
    return pytesseract


def _get_pdf2image():
    try:
        from pdf2image import convert_from_path
    except Exception as exc:
        raise OcrDependencyError("pdf2image non installato") from exc
    return convert_from_path
