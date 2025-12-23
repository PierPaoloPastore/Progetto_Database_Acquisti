"""
Parser per file XML FatturaPA.

Questo modulo fornisce:
- DTO (Data Transfer Object) per rappresentare in modo neutro i dati estratti
- una funzione principale `parse_invoice_xml(path)` che restituisce un `InvoiceDTO`
- supporto per file P7M (firme digitali PKCS#7)

Obiettivo:
- leggere i nodi essenziali dell'XML FatturaPA (CedentePrestatore, DatiGeneraliDocumento,
  DettaglioLinee, DatiRiepilogo, DatiPagamento)
- restituire una struttura dati pronta per essere usata dai servizi di import
  (app.services.import_service) che si occuperanno di mappare i DTO sui modelli SQLAlchemy.

Il parser è pensato per essere:
- tollerante ai campi mancanti (ritorna None dove appropriato)
- indipendente dai namespace (uso di local-name() negli XPath)
- capace di gestire file .xml e .p7m automaticamente
"""

from __future__ import annotations

import base64
import tempfile
import subprocess
import shutil
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

from lxml import etree
import os
import re
import logging
import time


# =========================
#  DTO (Data Transfer Objects)
# =========================


@dataclass
class SupplierDTO:
    """Dati essenziali del fornitore (CedentePrestatore)."""

    name: Optional[str] = None
    vat_number: Optional[str] = None
    fiscal_code: Optional[str] = None
    sdi_code: Optional[str] = None
    pec_email: Optional[str] = None
    email: Optional[str] = None

    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None


@dataclass
class InvoiceLineDTO:
    """Dati di una riga fattura (DettaglioLinee)."""

    line_number: Optional[int] = None
    description: Optional[str] = None

    quantity: Optional[Decimal] = None
    unit_of_measure: Optional[str] = None
    unit_price: Optional[Decimal] = None
    discount_amount: Optional[Decimal] = None
    discount_percent: Optional[Decimal] = None

    taxable_amount: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    total_line_amount: Optional[Decimal] = None

    sku_code: Optional[str] = None
    internal_code: Optional[str] = None


@dataclass
class VatSummaryDTO:
    """Dati del riepilogo IVA (DatiRiepilogo)."""

    vat_rate: Decimal
    taxable_amount: Decimal
    vat_amount: Decimal
    vat_nature: Optional[str] = None


@dataclass
class PaymentDTO:
    """Dati di una scadenza/pagamento previsto (DettaglioPagamento)."""

    due_date: Optional[date] = None
    expected_amount: Optional[Decimal] = None
    payment_terms: Optional[str] = None
    payment_method: Optional[str] = None


@dataclass
class InvoiceDTO:
    """
    DTO principale che aggrega tutti i dati della fattura.

    Non contiene logica di persistenza: sarà il servizio di import a trasformarlo
    in oggetti SQLAlchemy (Supplier, Invoice, InvoiceLine, VatSummary, Payment, ...).
    """

    supplier: SupplierDTO

    invoice_number: Optional[str] = None
    invoice_series: Optional[str] = None
    invoice_date: Optional[date] = None
    registration_date: Optional[date] = None

    currency: str = "EUR"
    total_taxable_amount: Optional[Decimal] = None
    total_vat_amount: Optional[Decimal] = None
    total_gross_amount: Optional[Decimal] = None

    # Scadenza principale derivata (eventualmente) dai DatiPagamento
    due_date: Optional[date] = None

    # Informazioni sul file sorgente
    file_name: Optional[str] = None
    file_hash: Optional[str] = None  # opzionale: può essere calcolato altrove

    # Riepilogo stato di import (lo useremo a livello modello come default)
    doc_status: str = "pending_physical_copy"
    payment_status: str = "unpaid"

    # Collezioni collegate
    lines: List[InvoiceLineDTO] = field(default_factory=list)
    vat_summaries: List[VatSummaryDTO] = field(default_factory=list)
    payments: List[PaymentDTO] = field(default_factory=list)
    attachments: List["AttachmentDTO"] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class AttachmentDTO:
    """Allegato FatturaPA (base64 + metadati)."""

    filename: Optional[str] = None
    description: Optional[str] = None
    format: Optional[str] = None
    compression: Optional[str] = None
    encryption: Optional[str] = None
    data_base64: Optional[str] = None


# =========================
#  Eccezioni specifiche
# =========================


class FatturaPAParseError(Exception):
    """Errore generico durante il parsing di una fattura XML."""


class P7MExtractionError(FatturaPAParseError):
    """Errore durante l'estrazione dell'XML da un file P7M."""


class FatturaPASkipFile(FatturaPAParseError):
    """File riconosciuto come non-fattura/metadato: da skippare senza errore DB."""


# =========================
#  Funzione principale di parsing
# =========================


def parse_invoice_xml(path: str | Path, *, validate_xsd: bool = False, logger: Optional[logging.Logger] = None) -> List[InvoiceDTO]:
    """
    Parsea un file XML FatturaPA e restituisce una lista di InvoiceDTO (1 per ogni Body).
    
    Supporta:
    - File .xml nativi
    - File .p7m (firma digitale PKCS#7)

    :param path: percorso del file XML o P7M
    :raises FatturaPAParseError: in caso di errore grave di parsing (es. XML non valido,
                                 nodi fondamentali mancanti).
    :raises P7MExtractionError: in caso di errore nell'estrazione da P7M
    """
    file_path = Path(path)

    if not file_path.is_file():
        raise FatturaPAParseError(f"File non trovato: {file_path}")

    # Gestione file P7M
    if _is_p7m_file(file_path):
        xml_content = _extract_xml_from_p7m(file_path)
        try:
            invoices = _parse_xml_bytes(
                xml_content,
                original_file_name=file_path.name,
                validate_xsd=validate_xsd,
                logger=logger,
            )
        except Exception as exc:
            _dump_debug_xml(xml_content, file_path.name, logger=logger)
            raise

        if _has_empty_invoices(invoices):
            openssl_xml = _extract_xml_from_p7m_openssl(file_path)
            if openssl_xml:
                try:
                    openssl_invoices = _parse_xml_bytes(
                        openssl_xml,
                        original_file_name=file_path.name,
                        validate_xsd=validate_xsd,
                        logger=logger,
                    )
                    if not _has_empty_invoices(openssl_invoices):
                        if logger:
                            logger.warning(
                                "P7M re-parsed with OpenSSL due to empty invoice content",
                                extra={"file": file_path.name},
                            )
                        return openssl_invoices
                except Exception:
                    pass

            _dump_empty_p7m_xml(xml_content, file_path.name, logger=logger)

        return invoices
    
    # File XML normale
    return _parse_xml_file(file_path, original_file_name=file_path.name, validate_xsd=validate_xsd, logger=logger)


def _parse_xml_bytes(xml_bytes: bytes, original_file_name: str, *, validate_xsd: bool, logger: Optional[logging.Logger]) -> List[InvoiceDTO]:
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
        tmp.write(xml_bytes)
        tmp_path = tmp.name
    try:
        return _parse_xml_file(Path(tmp_path), original_file_name=original_file_name, validate_xsd=validate_xsd, logger=logger)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _has_empty_invoices(invoices: List[InvoiceDTO]) -> bool:
    for inv in invoices:
        total = inv.total_gross_amount
        has_totals = total is not None and total != Decimal("0")
        if not inv.lines and not inv.vat_summaries and not has_totals:
            if inv.warnings is not None:
                inv.warnings.append("Documento senza righe/riepilogo: controllare estrazione P7M")
            return True
    return False


def _localname(tag: str | None) -> str:
    """Restituisce il local-name di un tag con/without namespace."""
    if not tag:
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    if ":" in tag:
        return tag.split(":", 1)[1]
    return tag


def _is_metadata_file(original_file_name: str, root) -> bool:
    """
    Riconosce file di metadati (non fatture) per evitare insert vuoti.
    Usa local-name del root per identificare FatturaElettronica.
    """
    name_lower = (original_file_name or "").lower()
    root_local = _localname(getattr(root, "tag", None)).lower()

    invoice_roots = {"fatturaelettronica", "fatturaelettronicabody"}
    metadata_roots = {"metadatifattura", "metadatinotifica", "metadato", "metadati"}
    notification_roots = {
        "ricevutaconsegna",
        "notificadecorrenzatermini",
        "notificaesitocommittente",
        "notificamancataconsegna",
        "notificascarico",
        "notificafileacv",
        "notificafiledecorrenza",
        "attestazionetrasmissionefattura",
        "notificafile",
    }

    # Se il root è FatturaElettronica, è fattura
    if root_local in invoice_roots:
        return False
    # Se il root è metadati/notifica, skip
    if root_local in metadata_roots or root_local in notification_roots:
        return True

    # Se il nome file suggerisce metadati e il root NON è fattura, skip
    if "metadato" in name_lower or "metadata" in name_lower:
        return True

    # Default: se non è riconosciuto come fattura, trattiamo come non-fattura/metadato
    return True


def _read_file_diagnostics(path: Path) -> dict:
    size = os.path.getsize(path)
    head_bytes = b""
    try:
        with open(path, "rb") as fh:
            head_bytes = fh.read(256)
    except Exception:
        head_bytes = b""

    encoding = None
    try:
        head_text = head_bytes.decode("latin-1", errors="replace")
        match = re.search(r'encoding=["\\\']([^"\\\']+)["\\\']', head_text, flags=re.IGNORECASE)
        if match:
            encoding = match.group(1)
    except Exception:
        encoding = None

    return {
        "size": size,
        "head_bytes": head_bytes,
        "encoding": encoding,
    }


def _dump_debug_xml(xml_bytes: bytes, original_file_name: str, logger: Optional[logging.Logger] = None):
    """
    Salva il blob XML problematico per debug manuale.
    """
    try:
        base_dir = Path(__file__).resolve().parents[2]
        out_dir = base_dir / "import_debug" / "p7m_failed"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        safe_name = original_file_name.replace(os.sep, "_")
        out_path = out_dir / f"{safe_name}.{ts}.xml"
        out_path.write_bytes(xml_bytes)
        if logger:
            logger.error("Dump XML estratto per debug P7M", extra={"file": original_file_name, "dump_path": str(out_path)})
    except Exception:
        if logger:
            logger.warning("Impossibile scrivere dump XML di debug", extra={"file": original_file_name})


def _dump_empty_p7m_xml(xml_bytes: bytes, original_file_name: str, logger: Optional[logging.Logger] = None):
    """
    Salva XML estratto quando il parsing produce un documento vuoto.
    """
    try:
        base_dir = Path(__file__).resolve().parents[2]
        out_dir = base_dir / "import_debug" / "p7m_empty"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        safe_name = original_file_name.replace(os.sep, "_")
        out_path = out_dir / f"{safe_name}.{ts}.xml"
        out_path.write_bytes(xml_bytes)
        if logger:
            logger.warning(
                "Dump XML per P7M vuoto",
                extra={"file": original_file_name, "dump_path": str(out_path)},
            )
    except Exception:
        if logger:
            logger.warning("Impossibile scrivere dump XML per P7M vuoto", extra={"file": original_file_name})


def _dump_encoding_failure(xml_bytes: bytes, original_file_name: str):
    """
    Salva XML che ha fallito i fallback di encoding.
    """
    try:
        base_dir = Path(__file__).resolve().parents[2]
        out_dir = base_dir / "import_debug" / "xml_encoding_failed"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        safe_name = original_file_name.replace(os.sep, "_")
        out_path = out_dir / f"{safe_name}.{ts}.xml"
        out_path.write_bytes(xml_bytes)
    except Exception:
        pass


def _validate_xsd(root, original_file_name: str, logger: Optional[logging.Logger] = None):
    """
    Valida il documento contro XSD ufficiale in modalità WARN (non blocca il parsing).
    """
    base_dir = Path(__file__).resolve().parents[2]  # repo root
    xsd_dir = base_dir / "resources" / "xsd"

    format_code = _get_text(root, ".//*[local-name()='FormatoTrasmissione']")
    schema_map = {
        "FPA12": "Schema_VFPA12_V1.2.3.xsd",
        "FPR12": "Schema_VFPR12_v1.2.3.xsd",
    }
    xsd_name = schema_map.get(format_code or "")
    if not xsd_name:
        return

    schema_path = xsd_dir / xsd_name
    if not schema_path.is_file():
        if logger:
            logger.warning(
                "XSD non trovato, skip validazione",
                extra={"file": original_file_name, "xsd": str(schema_path)},
            )
        return

    try:
        with open(schema_path, "rb") as fh:
            xmlschema_doc = etree.parse(fh)
        xmlschema = etree.XMLSchema(xmlschema_doc)
        if not xmlschema.validate(root):
            if logger:
                logger.warning(
                    "Validazione XSD fallita (WARN, non bloccante)",
                    extra={
                        "file": original_file_name,
                        "xsd": str(schema_path),
                        "errors": [str(e) for e in xmlschema.error_log[:5]],
                    },
                )
    except Exception as exc:
        if logger:
            logger.warning(
                "Errore durante validazione XSD (WARN, non bloccante)",
                extra={
                    "file": original_file_name,
                    "xsd": str(schema_path),
                    "error": str(exc),
                },
            )


def _load_xml_root(xml_path: Path, original_file_name: str):
    """
    Carica il root XML con diagnostica robusta.
    - Non silenzia gli errori di parsing.
    - Prova fallback rimuovendo control char non ammessi.
    Restituisce (root, used_fallback: bool).
    """
    diagnostics = _read_file_diagnostics(xml_path)
    head_repr = repr(diagnostics["head_bytes"])

    parser = etree.XMLParser(recover=False)
    try:
        tree = etree.parse(str(xml_path), parser)
        return tree.getroot(), False
    except Exception as exc:
        # Tentativo di fallback ripulendo i control char
        try:
            data = xml_path.read_bytes()
            clean = bytes(b for b in data if b in (9, 10, 13) or b >= 32)
            removed = len(data) - len(clean)
        except Exception as read_exc:
            raise FatturaPAParseError(
                f"XML non parsabile: file={original_file_name} size={diagnostics['size']} "
                f"parse_error={exc} head_bytes={head_repr} encoding={diagnostics['encoding']} "
                f"(lettura fallita per fallback: {read_exc})"
            ) from exc

        # Fallback per errori UTF-8 dichiarato ma bytes cp1252/latin-1
        from lxml.etree import XMLSyntaxError
        if isinstance(exc, XMLSyntaxError) and "not proper UTF-8" in str(exc):
            enc_attempts = [
                ("cp1252", "strict", False),
                ("latin-1", "strict", False),
                ("cp1252", "replace", True),
                ("latin-1", "replace", True),
            ]
            for enc, mode, use_recover in enc_attempts:
                try:
                    text = clean.decode(enc, errors=mode)
                    utf8_bytes = _clean_xml_bytes(text.encode("utf-8", errors="strict"))
                    if use_recover:
                        parser_recover = etree.XMLParser(recover=True)
                        root = etree.fromstring(utf8_bytes, parser=parser_recover)
                    else:
                        root = etree.fromstring(utf8_bytes)
                    logger = logging.getLogger(__name__)
                    logger.warning(
                        "XML encoding fallback applied",
                        extra={
                            "file": original_file_name,
                            "fallback_encoding": enc,
                            "fallback_mode": mode,
                            "removed_bytes": removed,
                        },
                    )
                    return root, True
                except Exception:
                    continue
            # Se fallisce, dump e errore
            _dump_encoding_failure(clean, original_file_name)
            raise FatturaPAParseError(
                f"XML non parsabile (encoding fallback fallito): file={original_file_name} size={diagnostics['size']} "
                f"parse_error={exc} head_bytes={head_repr} encoding={diagnostics['encoding']} removed_bytes={removed}"
            ) from exc

        try:
            root = etree.fromstring(clean)
            # Log minimale sul fallback per debug (logger opzionale se configurato)
            logger = logging.getLogger(__name__)
            logger.warning(
                "XML ripulito da control chars",
                extra={
                    "file": original_file_name,
                    "removed_bytes": removed,
                },
            )
            return root, True
        except Exception as fallback_exc:
            # Ultimo tentativo: recover=True
            try:
                parser_recover = etree.XMLParser(recover=True)
                root = etree.fromstring(clean, parser=parser_recover)
                logger = logging.getLogger(__name__)
                logger.warning(
                    "XML parsed with recover=True (ultima spiaggia)",
                    extra={"file": original_file_name, "removed_bytes": removed},
                )
                return root, True
            except Exception:
                _dump_encoding_failure(clean, original_file_name)
                raise FatturaPAParseError(
                    f"XML non parsabile: file={original_file_name} size={diagnostics['size']} "
                    f"parse_error={exc} head_bytes={head_repr} encoding={diagnostics['encoding']} "
                    f"fallback_error={fallback_exc} removed_bytes={removed}"
                ) from fallback_exc


def _parse_xml_file(xml_path: Path, original_file_name: str, *, validate_xsd: bool = False, logger: Optional[logging.Logger] = None) -> List[InvoiceDTO]:
    """
    Parsing effettivo del file XML.
    
    :param xml_path: percorso del file XML da parsare
    :param original_file_name: nome originale del file (usato nel DTO)
    """
    root, used_fallback = _load_xml_root(xml_path, original_file_name)

    # Skip file di metadati o non-fatture
    if root is None or _is_metadata_file(original_file_name, root):
        raise FatturaPASkipFile(
            f"File non riconosciuto come fattura (metadati/altro XML): "
            f"file={original_file_name}, root={getattr(root, 'tag', None)}"
        )

    # Validazione XSD opzionale (WARN)
    if validate_xsd:
        _validate_xsd(root, original_file_name, logger=logger)

    # Prendiamo tutti i FatturaElettronicaBody disponibili
    bodies = root.xpath(".//*[local-name()='FatturaElettronicaBody']")
    if not bodies:
        bodies = [root]

    base_warnings: List[str] = []
    supplier_dto = _parse_supplier(root, base_warnings)
    invoices: List[InvoiceDTO] = []

    for idx, body in enumerate(bodies, start=1):
        warnings: List[str] = list(base_warnings)

        (
            invoice_number,
            invoice_series,
            invoice_date,
            currency,
            total_gross_amount,
            general_rounding,
        ) = _parse_invoice_header(body, original_file_name)

        lines_dto = _parse_invoice_lines(body)
        vat_summaries_dto, total_taxable, total_vat = _parse_vat_summaries(body)
        payments_dto, main_due_date = _parse_payments(body)
        attachments_dto = _parse_attachments(body, warnings)

        # Calcolo totale con fallback
        computed_total = total_gross_amount
        if computed_total is None and total_taxable is not None and total_vat is not None:
            computed_total = total_taxable + total_vat + (general_rounding or Decimal("0"))
        if computed_total is None:
            # fallback emergenza da linee
            sum_lines = sum((ln.total_line_amount or Decimal("0")) for ln in lines_dto)
            computed_total = sum_lines
            warnings.append("ImportoTotaleDocumento assente: ricostruito da linee (non conforme)")

        # Warning se body multipli in unico file (per tracciabilità)
        if len(bodies) > 1:
            warnings.append(f"Body multipli nel file: body_index={idx}/{len(bodies)}")

        invoice_dto = InvoiceDTO(
            supplier=supplier_dto,
            invoice_number=invoice_number,
            invoice_series=invoice_series,
            invoice_date=invoice_date,
            registration_date=None,
            currency=currency or "EUR",
            total_taxable_amount=total_taxable,
            total_vat_amount=total_vat,
            total_gross_amount=computed_total,
            due_date=main_due_date,
            file_name=original_file_name,
            file_hash=None,
            doc_status="pending_physical_copy",
            payment_status="unpaid",
            lines=lines_dto,
            vat_summaries=vat_summaries_dto,
            payments=payments_dto,
            attachments=attachments_dto,
            warnings=warnings,
        )

        invoices.append(invoice_dto)

    return invoices


# =========================
#  Gestione file P7M
# =========================


def _is_p7m_file(file_path: Path) -> bool:
    """
    Verifica se un file è un P7M basandosi sull'estensione.
    """
    return file_path.suffix.lower() in ['.p7m']


def _extract_xml_from_p7m(p7m_path: Path) -> bytes:
    """
    Estrae il contenuto XML da un file P7M.
    
    I file FatturaPA P7M contengono l'XML codificato in Base64
    all'interno di una struttura di firma digitale PKCS#7.
    
    :param p7m_path: percorso del file P7M
    :return: contenuto XML come bytes
    :raises P7MExtractionError: se l'estrazione fallisce
    """

    openssl_xml = _extract_xml_from_p7m_openssl(p7m_path)
    if openssl_xml:
        return openssl_xml

    try:
        data = p7m_path.read_bytes()

        def _is_base64ish(buf: bytes) -> bool:
            allowed = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\r\n"
            return all(b in allowed for b in buf)

        path_used = "base64" if _is_base64ish(data) else "der"

        if path_used == "base64":
            cleaned = b"".join(data.split())
            missing_padding = len(cleaned) % 4
            if missing_padding:
                cleaned += b"=" * (4 - missing_padding)
            decoded = base64.b64decode(cleaned, validate=False)
        else:
            decoded = data

        xml_start = _find_xml_start(decoded)
        if xml_start < 0:
            head = repr(decoded[:200])
            raise P7MExtractionError(
                f"Contenuto XML non trovato nel file P7M: file={p7m_path.name} size={len(data)} head_bytes={head} path={path_used}"
            )

        xml_end = _find_xml_end(decoded, xml_start)
        if xml_end <= xml_start:
            head = repr(decoded[xml_start:xml_start+200])
            raise P7MExtractionError(
                f"Fine XML non trovata nel file P7M: file={p7m_path.name} size={len(data)} head_xml={head} path={path_used}"
            )

        xml_content = decoded[xml_start:xml_end]
        xml_content = _clean_xml_bytes(xml_content)
        return xml_content

    except base64.binascii.Error as exc:
        openssl_xml = _extract_xml_from_p7m_openssl(p7m_path)
        if openssl_xml:
            return openssl_xml
        raise P7MExtractionError(
            f"Errore decodifica Base64 del file P7M: {exc}"
        ) from exc
    except Exception as exc:
        openssl_xml = _extract_xml_from_p7m_openssl(p7m_path)
        if openssl_xml:
            return openssl_xml
        raise P7MExtractionError(
            f"Errore durante l'estrazione XML da P7M: {exc}"
        ) from exc


def _extract_xml_from_p7m_openssl(p7m_path: Path) -> Optional[bytes]:
    openssl_bin = os.environ.get("OPENSSL_BIN") or shutil.which("openssl")
    if not openssl_bin:
        return None
    for inform in ("DER", "PEM"):
        try:
            with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp_out:
                out_path = tmp_out.name
            result = subprocess.run(
                [
                    openssl_bin,
                    "smime",
                    "-verify",
                    "-in",
                    str(p7m_path),
                    "-inform",
                    inform,
                    "-noverify",
                    "-out",
                    out_path,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and Path(out_path).is_file():
                data = Path(out_path).read_bytes()
                Path(out_path).unlink(missing_ok=True)
                return _clean_xml_bytes(data)
            Path(out_path).unlink(missing_ok=True)
        except Exception:
            try:
                Path(out_path).unlink(missing_ok=True)
            except Exception:
                pass
            continue
    return None


def _clean_xml_bytes(data: bytes) -> bytes:
    """
    Rimuove caratteri invalidi XML dal contenuto binario.
    
    Rimuove solo byte NUL e control < 0x20 esclusi \t, \n, \r.
    Non decodifica/re-encoda il contenuto.
    """
    allowed_ctrl = {9, 10, 13}
    cleaned = bytearray()
    for b in data:
        if b == 0:
            continue
        if b < 0x20 and b not in allowed_ctrl:
            continue
        cleaned.append(b)
    return _strip_invalid_tag_bytes(bytes(cleaned))


def _strip_invalid_tag_bytes(data: bytes) -> bytes:
    """
    Elimina byte non ASCII dai nomi dei tag (caso P7M con byte corrotti).
    """
    allowed = set(b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:.-")
    out = bytearray()
    i = 0
    length = len(data)
    while i < length:
        b = data[i]
        if b != 0x3C:  # '<'
            out.append(b)
            i += 1
            continue

        out.append(b)
        i += 1
        if i >= length:
            break

        next_b = data[i]
        if next_b in (0x3F, 0x21):  # '?' o '!' (PI, commenti, doctype)
            while i < length:
                out.append(data[i])
                if data[i] == 0x3E:  # '>'
                    i += 1
                    break
                i += 1
            continue

        if next_b == 0x2F:  # '/'
            out.append(next_b)
            i += 1

        while i < length:
            b2 = data[i]
            if b2 == 0x3E or b2 == 0x2F or b2 <= 0x20:
                break
            if b2 in allowed:
                out.append(b2)
            i += 1

        while i < length:
            b2 = data[i]
            out.append(b2)
            i += 1
            if b2 == 0x3E:
                break

    return bytes(out)


def _find_xml_start(data: bytes) -> int:
    """
    Cerca l'offset di inizio dell'XML nel binario decodificato.
    
    Prova diversi pattern comuni:
    - <?xml
    - <p:FatturaElettronica
    - <FatturaElettronica
    """
    patterns = [
        b'<?xml',
        b'<p:FatturaElettronica',
        b'<FatturaElettronica',
    ]
    
    for pattern in patterns:
        pos = data.find(pattern)
        if pos >= 0:
            return pos
    
    return -1


def _find_xml_end(data: bytes, start: int) -> int:
    """
    Cerca l'offset di fine dell'XML nel binario decodificato.
    
    Cerca i tag di chiusura più comuni, prendendo il più lontano
    (per includere anche eventuali firme digitali XML Signature).
    """
    endings = [
        b'</FatturaElettronica>',
        b'</p:FatturaElettronica>',
        b'</ds:Signature>',
    ]
    
    max_end = -1
    
    for ending in endings:
        pos = data.rfind(ending)
        if pos > start:
            end_pos = pos + len(ending)
            if end_pos > max_end:
                max_end = end_pos
    
    return max_end


# =========================
#  Funzioni di supporto (private)
# =========================


def _first(node, xpath: str):
    """Restituisce il primo nodo che soddisfa l'XPath, oppure None."""
    res = node.xpath(xpath)
    return res[0] if res else None


def _get_text(node, xpath: str) -> Optional[str]:
    """Restituisce il testo del primo nodo trovato, ripulito, oppure None."""
    if node is None:
        return None
    target = _first(node, xpath)
    if target is None or target.text is None:
        return None
    text = target.text.strip()
    return text or None


def _to_decimal(value: Optional[str]) -> Optional[Decimal]:
    """Converte una stringa in Decimal, restituendo None se vuota o non valida."""
    if not value:
        return None
    try:
        return Decimal(value.replace(",", "."))
    except (InvalidOperation, AttributeError):
        return None


def _to_int(value: Optional[str]) -> Optional[int]:
    """Converte una stringa in int, restituendo None in caso di errore."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _to_date(value: Optional[str]) -> Optional[date]:
    """Converte una stringa 'YYYY-MM-DD' in date, restituendo None se non valida."""
    if not value:
        return None
    try:
        year, month, day = value.split("-")
        return date(int(year), int(month), int(day))
    except Exception:
        return None


# ---------- Supplier ----------


def _parse_supplier(root, warnings: Optional[List[str]] = None) -> SupplierDTO:
    """
    Estrae i dati del fornitore (CedentePrestatore).

    Percorso tipico:
    FatturaElettronica/FatturaElettronicaHeader/CedentePrestatore
    """
    supplier_node = _first(root, ".//*[local-name()='CedentePrestatore']")

    if supplier_node is None:
        # In teoria è obbligatorio, ma possiamo almeno evitare crash
        return SupplierDTO(name="Fornitore sconosciuto")

    # Dati anagrafici
    denominazione = _get_text(supplier_node, ".//*[local-name()='Denominazione']")
    nome = _get_text(supplier_node, ".//*[local-name()='Nome']")
    cognome = _get_text(supplier_node, ".//*[local-name()='Cognome']")

    if denominazione:
        name = denominazione
    elif nome or cognome:
        name = " ".join(filter(None, [nome, cognome])).strip()
    else:
        name = None

    # IVA e CF
    vat_number = _get_text(
        supplier_node,
        ".//*[local-name()='IdFiscaleIVA']/*[local-name()='IdCodice']",
    )
    fiscal_code = _get_text(supplier_node, ".//*[local-name()='CodiceFiscale']")

    # Contatti del CedentePrestatore (mittente)
    email = _get_text(supplier_node, ".//*[local-name()='Contatti']/*[local-name()='Email']")
    pec_email = _get_text(supplier_node, ".//*[local-name()='Contatti']/*[local-name()='PEC']")

    # Sede
    address = _get_text(supplier_node, ".//*[local-name()='Sede']/*[local-name()='Indirizzo']")
    postal_code = _get_text(
        supplier_node, ".//*[local-name()='Sede']/*[local-name()='CAP']"
    )
    city = _get_text(
        supplier_node, ".//*[local-name()='Sede']/*[local-name()='Comune']"
    )
    province = _get_text(
        supplier_node, ".//*[local-name()='Sede']/*[local-name()='Provincia']"
    )
    country = _get_text(
        supplier_node, ".//*[local-name()='Sede']/*[local-name()='Nazione']"
    )
    
    # Fallback: se manca il nome ma abbiamo P.IVA/CF, usa quello
    if not name:
        if vat_number:
            name = f"P.IVA {vat_number}"
        elif fiscal_code:
            name = f"CF {fiscal_code}"
        else:
            name = "Fornitore sconosciuto"
        if warnings is not None:
            warnings.append("Anagrafica fornitore incompleta: usato fallback identificativo")

    return SupplierDTO(
        name=name,
        vat_number=vat_number,
        fiscal_code=fiscal_code,
        sdi_code=None,
        pec_email=pec_email,
        email=email,
        address=address,
        postal_code=postal_code,
        city=city,
        province=province,
        country=country,
    )


# ---------- Testata fattura ----------


def _parse_invoice_header(body, original_file_name: str) -> tuple[
    Optional[str], Optional[str], Optional[date], Optional[str], Optional[Decimal], Optional[Decimal]
]:
    """
    Estrae i dati principali del documento (DatiGeneraliDocumento):

    - Numero
    - Divisa
    - Data
    - ImportoTotaleDocumento
    - Arrotondamento
    """
    dg_node = _first(body, ".//*[local-name()='DatiGeneraliDocumento']")

    if dg_node is None:
        # Mancano i dati generali: consideriamo il file non valido come fattura
        raise FatturaPAParseError(
            f"DatiGeneraliDocumento assente: file non valido come fattura. "
            f"file={original_file_name}, root={getattr(body, 'tag', None)}"
        )

    invoice_number = _get_text(dg_node, ".//*[local-name()='Numero']")
    invoice_date_str = _get_text(dg_node, ".//*[local-name()='Data']")
    invoice_date = _to_date(invoice_date_str)

    currency = _get_text(dg_node, ".//*[local-name()='Divisa']")
    total_gross_str = _get_text(
        dg_node, ".//*[local-name()='ImportoTotaleDocumento']"
    )
    total_gross = _to_decimal(total_gross_str)
    general_rounding = _to_decimal(_get_text(dg_node, ".//*[local-name()='Arrotondamento']"))

    # Serie (non sempre presente esplicita; talvolta è incorporata nel Numero)
    invoice_series = None  # Manteniamo questo campo per possibili estensioni future

    return invoice_number, invoice_series, invoice_date, currency, total_gross, general_rounding


# ---------- DettaglioLinee ----------


def _parse_invoice_lines(body) -> List[InvoiceLineDTO]:
    """
    Estrae le righe fattura (DettaglioLinee).

    Restituisce una lista di InvoiceLineDTO.
    """
    lines: List[InvoiceLineDTO] = []

    if body is None:
        return lines

    line_nodes = body.xpath(".//*[local-name()='DettaglioLinee']")

    for ln_node in line_nodes:
        line_number = _to_int(
            _get_text(ln_node, ".//*[local-name()='NumeroLinea']")
        )
        description = _get_text(ln_node, ".//*[local-name()='Descrizione']")

        quantity = _to_decimal(
            _get_text(ln_node, ".//*[local-name()='Quantita']")
        )
        unit_of_measure = _get_text(
            ln_node, ".//*[local-name()='UnitaMisura']"
        )
        unit_price = _to_decimal(
            _get_text(ln_node, ".//*[local-name()='PrezzoUnitario']")
        )

        # Sconti
        discount_amount = _to_decimal(
            _get_text(
                ln_node,
                ".//*[local-name()='ScontoMaggiorazione']/*[local-name()='Importo']",
            )
        )
        discount_percent = _to_decimal(
            _get_text(
                ln_node,
                ".//*[local-name()='ScontoMaggiorazione']/*[local-name()='Percentuale']",
            )
        )

        # Totali e IVA
        taxable_amount = _to_decimal(
            _get_text(ln_node, ".//*[local-name()='ImponibileImporto']")
        )
        vat_rate = _to_decimal(
            _get_text(ln_node, ".//*[local-name()='AliquotaIVA']")
        )
        vat_amount = _to_decimal(
            _get_text(ln_node, ".//*[local-name()='Imposta']")
        )
        total_line_amount = _to_decimal(
            _get_text(ln_node, ".//*[local-name()='PrezzoTotale']")
        )

        # Codici articolo
        sku_code = _get_text(
            ln_node,
            ".//*[local-name()='CodiceArticolo']/*[local-name()='CodiceValore']",
        )
        internal_code = None  # Potremmo raffinare

        lines.append(
            InvoiceLineDTO(
                line_number=line_number,
                description=description,
                quantity=quantity,
                unit_of_measure=unit_of_measure,
                unit_price=unit_price,
                discount_amount=discount_amount,
                discount_percent=discount_percent,
                taxable_amount=taxable_amount,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                total_line_amount=total_line_amount,
                sku_code=sku_code,
                internal_code=internal_code,
            )
        )

    return lines


# ---------- DatiRiepilogo ----------


def _parse_vat_summaries(body) -> tuple[
    List[VatSummaryDTO], Optional[Decimal], Optional[Decimal]
]:
    """
    Estrae il riepilogo IVA (DatiRiepilogo).

    Restituisce:
    - lista di VatSummaryDTO
    - totale imponibile (somma ImponibileImporto)
    - totale IVA (somma Imposta)
    """
    summaries: List[VatSummaryDTO] = []
    total_taxable = Decimal("0")
    total_vat = Decimal("0")

    summary_nodes = body.xpath(".//*[local-name()='DatiRiepilogo']")

    for s_node in summary_nodes:
        vat_rate = _to_decimal(
            _get_text(s_node, ".//*[local-name()='AliquotaIVA']")
        )
        taxable_amount = _to_decimal(
            _get_text(s_node, ".//*[local-name()='ImponibileImporto']")
        )
        vat_amount = _to_decimal(
            _get_text(s_node, ".//*[local-name()='Imposta']")
        )
        vat_nature = _get_text(s_node, ".//*[local-name()='Natura']")

        if vat_rate is None or taxable_amount is None or vat_amount is None:
            # Se mancano dati essenziali, saltiamo la riga per evitare
            # di inquinare i totali
            continue

        summaries.append(
            VatSummaryDTO(
                vat_rate=vat_rate,
                taxable_amount=taxable_amount,
                vat_amount=vat_amount,
                vat_nature=vat_nature,
            )
        )

        total_taxable += taxable_amount
        total_vat += vat_amount

    # Se non ci sono riepiloghi validi, restituiamo None per i totali
    if not summaries:
        return [], None, None

    return summaries, total_taxable, total_vat


# ---------- DatiPagamento / DettaglioPagamento ----------


def _parse_payments(body) -> tuple[List[PaymentDTO], Optional[date]]:
    """
    Estrae le informazioni di pagamento (DatiPagamento/DettaglioPagamento).

    Restituisce:
    - lista di PaymentDTO
    - data di scadenza principale (il minimo tra le date trovate)
    """
    payments: List[PaymentDTO] = []

    payment_nodes = body.xpath(".//*[local-name()='DettaglioPagamento']")

    for p_node in payment_nodes:
        due_date_str = _get_text(
            p_node, ".//*[local-name()='DataScadenzaPagamento']"
        )
        due_date = _to_date(due_date_str)

        expected_amount = _to_decimal(
            _get_text(p_node, ".//*[local-name()='ImportoPagamento']")
        )

        payment_terms = _get_text(
            p_node, ".//*[local-name()='TerminiPagamento']"
        )
        payment_method = _get_text(
            p_node, ".//*[local-name()='ModalitaPagamento']"
        )

        payments.append(
            PaymentDTO(
                due_date=due_date,
                expected_amount=expected_amount,
                payment_terms=payment_terms,
                payment_method=payment_method,
            )
        )

    # Scadenza principale: la più vicina (data minima)
    main_due_date: Optional[date] = None
    for p in payments:
        if p.due_date is None:
            continue
        if main_due_date is None or p.due_date < main_due_date:
            main_due_date = p.due_date

    return payments, main_due_date


def _parse_attachments(body, warnings: Optional[List[str]] = None) -> List[AttachmentDTO]:
    """
    Estrae gli allegati (Allegati) dal body.
    """
    attachments: List[AttachmentDTO] = []
    if body is None:
        return attachments

    nodes = body.xpath(".//*[local-name()='Allegati']")
    for node in nodes:
        filename = _get_text(node, ".//*[local-name()='NomeAttachment']")
        description = _get_text(node, ".//*[local-name()='DescrizioneAttachment']")
        format_name = _get_text(node, ".//*[local-name()='FormatoAttachment']")
        compression = _get_text(node, ".//*[local-name()='AlgoritmoCompressione']")
        encryption = _get_text(node, ".//*[local-name()='AlgoritmoCrittografia']")
        data_base64 = _get_text(node, ".//*[local-name()='Attachment']")

        if not any([filename, description, format_name, compression, encryption, data_base64]):
            continue

        if data_base64 is None and warnings is not None:
            warnings.append("Allegato presente senza contenuto base64")

        attachments.append(
            AttachmentDTO(
                filename=filename,
                description=description,
                format=format_name,
                compression=compression,
                encryption=encryption,
                data_base64=data_base64,
            )
        )

    return attachments
