"""
Parser FatturaPA basato su XSD ufficiali (xsdata).

Usa le classi generate in app/parsers/xsd_generated e mappa i dati
nei DTO esistenti per compatibilita' con i servizi.
"""

from __future__ import annotations

from dataclasses import is_dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional, Sequence

from lxml import etree
from xsdata.formats.dataclass.context import XmlContext
from xsdata.formats.dataclass.parsers import XmlParser
from xsdata.formats.dataclass.parsers.config import ParserConfig

from app.parsers.xsd_generated import vfpa12, vfpr12, vfsm10
from app.parsers.fatturapa_parser import (
    AttachmentDTO,
    FatturaPAParseError,
    FatturaPASkipFile,
    InvoiceDTO,
    InvoiceLineDTO,
    PaymentDTO,
    P7MExtractionError,
    SupplierDTO,
    VatSummaryDTO,
    _clean_xml_bytes,
    _extract_xml_from_p7m,
    parse_invoice_xml as legacy_parse_invoice_xml,
)


def parse_invoice_xml(
    path: str | Path, *, validate_xsd: bool = False, logger: Optional[object] = None
) -> List[InvoiceDTO]:
    """
    Parsea un file XML/P7M FatturaPA usando XSD (xsdata) e restituisce i DTO.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FatturaPAParseError(f"File non trovato: {file_path}")

    if _is_p7m_file(file_path):
        xml_bytes = _extract_xml_from_p7m(file_path)
    else:
        xml_bytes = file_path.read_bytes()

    try:
        root, xml_bytes = _load_xml_root(xml_bytes, file_path.name, logger=logger)
    except FatturaPAParseError as exc:
        legacy_invoices = _fallback_to_legacy_parser(
            file_path,
            validate_xsd=validate_xsd,
            logger=logger,
            reason=f"root_parse_error={exc}",
        )
        if legacy_invoices is not None:
            return legacy_invoices
        raise
    if root is None or _is_metadata_file(file_path.name, root):
        raise FatturaPASkipFile(
            f"File non riconosciuto come fattura (metadati/altro XML): "
            f"file={file_path.name}, root={getattr(root, 'tag', None)}"
        )

    format_code = _get_text(root, ".//*[local-name()='FormatoTrasmissione']")
    model = _select_model(format_code)

    parser = XmlParser(
        context=XmlContext(),
        config=ParserConfig(
            fail_on_unknown_properties=False,
            fail_on_converter_warnings=False,
        ),
    )
    try:
        doc = parser.from_bytes(xml_bytes, model)
    except Exception as exc:
        legacy_invoices = _fallback_to_legacy_parser(
            file_path,
            validate_xsd=validate_xsd,
            logger=logger,
            reason=f"xsdata_error={exc}",
        )
        if legacy_invoices is not None:
            return legacy_invoices
        raise FatturaPAParseError(f"XML non parsabile (xsdata): {exc}") from exc

    bodies = getattr(doc, "fattura_elettronica_body", None) or []
    if not bodies:
        legacy_invoices = _fallback_to_legacy_parser(
            file_path,
            validate_xsd=validate_xsd,
            logger=logger,
            reason="xsdata_empty_body",
        )
        if legacy_invoices is not None:
            return legacy_invoices
        raise FatturaPAParseError(
            f"Nessun FatturaElettronicaBody trovato: file={file_path.name}"
        )

    return _map_document(doc, file_path.name)


def _fallback_to_legacy_parser(
    file_path: Path,
    *,
    validate_xsd: bool,
    logger: Optional[object],
    reason: str,
) -> Optional[List[InvoiceDTO]]:
    try:
        invoices = legacy_parse_invoice_xml(
            file_path,
            validate_xsd=validate_xsd,
            logger=logger,
        )
    except FatturaPASkipFile:
        raise
    except Exception as exc:
        if logger:
            logger.warning(
                "Legacy parser fallback failed",
                extra={"file": file_path.name, "reason": reason, "error": str(exc)},
            )
        return None

    if logger:
        logger.warning(
            "Legacy parser fallback used",
            extra={"file": file_path.name, "reason": reason},
        )

    return invoices


def _select_model(format_code: Optional[str]):
    code = (format_code or "").upper()
    if code == "FPA12":
        return vfpa12.FatturaElettronica
    if code == "FSM10" or code == "VFSM10":
        return vfsm10.FatturaElettronicaSemplificata
    return vfpr12.FatturaElettronica


def _map_document(doc, original_file_name: str) -> List[InvoiceDTO]:
    header = getattr(doc, "fattura_elettronica_header", None)
    bodies = getattr(doc, "fattura_elettronica_body", None) or []

    supplier_dto = _map_supplier(header)

    invoices: List[InvoiceDTO] = []
    for idx, body in enumerate(bodies, start=1):
        invoice_dto = _map_body(
            body=body,
            supplier_dto=supplier_dto,
            original_file_name=original_file_name,
        )
        if len(bodies) > 1:
            invoice_dto.warnings.append(
                f"Body multipli nel file: body_index={idx}/{len(bodies)}"
            )
        invoices.append(invoice_dto)

    if not invoices:
        raise FatturaPAParseError(
            f"Nessun FatturaElettronicaBody trovato: file={original_file_name}"
        )

    return invoices


def _map_supplier(header) -> SupplierDTO:
    if not header:
        return SupplierDTO(name="Fornitore sconosciuto")

    cedente = getattr(header, "cedente_prestatore", None)
    if not cedente:
        return SupplierDTO(name="Fornitore sconosciuto")

    dati_anag = getattr(cedente, "dati_anagrafici", None)
    anagrafica = getattr(dati_anag, "anagrafica", None)

    denominazione = getattr(anagrafica, "denominazione", None)
    nome = getattr(anagrafica, "nome", None)
    cognome = getattr(anagrafica, "cognome", None)
    if denominazione:
        name = denominazione
    elif nome or cognome:
        name = " ".join(filter(None, [nome, cognome])).strip()
    else:
        name = None

    id_fiscale = getattr(dati_anag, "id_fiscale_iva", None)
    vat_number = getattr(id_fiscale, "id_codice", None)
    fiscal_code = getattr(dati_anag, "codice_fiscale", None)

    contatti = getattr(cedente, "contatti", None)
    email = getattr(contatti, "email", None)
    pec_email = getattr(contatti, "pec", None)

    sede = getattr(cedente, "sede", None)
    address = getattr(sede, "indirizzo", None)
    postal_code = getattr(sede, "cap", None)
    city = getattr(sede, "comune", None)
    province = getattr(sede, "provincia", None)
    country = getattr(sede, "nazione", None)

    if not name:
        if vat_number:
            name = f"P.IVA {vat_number}"
        elif fiscal_code:
            name = f"CF {fiscal_code}"
        else:
            name = "Fornitore sconosciuto"

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


def _map_body(body, supplier_dto: SupplierDTO, original_file_name: str) -> InvoiceDTO:
    warnings: List[str] = []

    dati_generali = getattr(body, "dati_generali", None)
    dati_generali_doc = getattr(dati_generali, "dati_generali_documento", None)
    if not dati_generali_doc:
        raise FatturaPAParseError(
            f"DatiGeneraliDocumento assente: file={original_file_name}"
        )

    invoice_number = getattr(dati_generali_doc, "numero", None)
    tipo_documento = _enum_to_str(getattr(dati_generali_doc, "tipo_documento", None))
    invoice_date = _to_date(getattr(dati_generali_doc, "data", None))
    currency = getattr(dati_generali_doc, "divisa", None) or "EUR"
    total_gross_amount = _to_decimal(
        getattr(dati_generali_doc, "importo_totale_documento", None)
    )
    general_rounding = _to_decimal(getattr(dati_generali_doc, "arrotondamento", None))

    lines_dto = _map_lines(body)
    vat_summaries_dto, total_taxable, total_vat = _map_vat_summaries(body)
    payments_dto, main_due_date = _map_payments(body)
    attachments_dto = _map_attachments(body, warnings)

    computed_total = total_gross_amount
    if computed_total is None and total_taxable is not None and total_vat is not None:
        computed_total = total_taxable + total_vat + (general_rounding or Decimal("0"))
    if computed_total is None:
        sum_lines = sum((ln.total_line_amount or Decimal("0")) for ln in lines_dto)
        computed_total = sum_lines
        warnings.append(
            "ImportoTotaleDocumento assente: ricostruito da linee (non conforme)"
        )

    return InvoiceDTO(
        supplier=supplier_dto,
        invoice_number=invoice_number,
        invoice_series=None,
        tipo_documento=tipo_documento,
        invoice_date=invoice_date,
        registration_date=None,
        currency=currency,
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


def _map_lines(body) -> List[InvoiceLineDTO]:
    result: List[InvoiceLineDTO] = []
    beni_servizi = getattr(body, "dati_beni_servizi", None)
    if not beni_servizi:
        return result

    for ln in getattr(beni_servizi, "dettaglio_linee", []) or []:
        line_number = getattr(ln, "numero_linea", None)
        description = getattr(ln, "descrizione", None)
        quantity = _to_decimal(getattr(ln, "quantita", None))
        unit_of_measure = getattr(ln, "unita_misura", None)
        unit_price = _to_decimal(getattr(ln, "prezzo_unitario", None))
        total_line_amount = _to_decimal(getattr(ln, "prezzo_totale", None))
        vat_rate = _to_decimal(getattr(ln, "aliquota_iva", None))

        result.append(
            InvoiceLineDTO(
                line_number=line_number,
                description=description,
                quantity=quantity,
                unit_of_measure=unit_of_measure,
                unit_price=unit_price,
                discount_amount=None,
                discount_percent=None,
                taxable_amount=total_line_amount,
                vat_rate=vat_rate,
                vat_amount=None,
                total_line_amount=total_line_amount,
                sku_code=None,
                internal_code=None,
            )
        )

    return result


def _map_vat_summaries(body) -> tuple[List[VatSummaryDTO], Optional[Decimal], Optional[Decimal]]:
    summaries: List[VatSummaryDTO] = []
    total_taxable = Decimal("0")
    total_vat = Decimal("0")

    beni_servizi = getattr(body, "dati_beni_servizi", None)
    if not beni_servizi:
        return [], None, None

    for s in getattr(beni_servizi, "dati_riepilogo", []) or []:
        vat_rate = _to_decimal(getattr(s, "aliquota_iva", None))
        taxable_amount = _to_decimal(getattr(s, "imponibile_importo", None))
        vat_amount = _to_decimal(getattr(s, "imposta", None))
        vat_nature = _enum_to_str(getattr(s, "natura", None))

        if vat_rate is None or taxable_amount is None or vat_amount is None:
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

    if not summaries:
        return [], None, None

    return summaries, total_taxable, total_vat


def _map_payments(body) -> tuple[List[PaymentDTO], Optional[date]]:
    payments: List[PaymentDTO] = []
    main_due_date: Optional[date] = None

    for dp in getattr(body, "dati_pagamento", []) or []:
        condizioni = _enum_to_str(getattr(dp, "condizioni_pagamento", None))
        for det in getattr(dp, "dettaglio_pagamento", []) or []:
            due_date = _to_date(getattr(det, "data_scadenza_pagamento", None))
            expected_amount = _to_decimal(getattr(det, "importo_pagamento", None))
            payment_method = _enum_to_str(getattr(det, "modalita_pagamento", None))

            payments.append(
                PaymentDTO(
                    due_date=due_date,
                    expected_amount=expected_amount,
                    payment_terms=condizioni,
                    payment_method=payment_method,
                )
            )

            if due_date and (main_due_date is None or due_date < main_due_date):
                main_due_date = due_date

    return payments, main_due_date


def _map_attachments(body, warnings: List[str]) -> List[AttachmentDTO]:
    attachments: List[AttachmentDTO] = []
    for att in getattr(body, "allegati", []) or []:
        data_base64 = getattr(att, "attachment", None)
        if data_base64 is None:
            warnings.append("Allegato presente senza contenuto base64")

        attachments.append(
            AttachmentDTO(
                filename=getattr(att, "nome_attachment", None),
                description=getattr(att, "descrizione_attachment", None),
                format=getattr(att, "formato_attachment", None),
                compression=getattr(att, "algoritmo_compressione", None),
                encryption=getattr(att, "algoritmo_crittografia", None),
                data_base64=data_base64,
            )
        )
    return attachments


def _is_p7m_file(file_path: Path) -> bool:
    return file_path.suffix.lower() == ".p7m"


def _load_xml_root(xml_bytes: bytes, file_name: str, logger: Optional[object] = None):
    cleaned = _clean_xml_bytes(xml_bytes)
    try:
        parser = etree.XMLParser(recover=True)
        return etree.fromstring(cleaned, parser=parser), cleaned
    except Exception as exc:
        try:
            from lxml.etree import XMLSyntaxError
        except Exception:
            XMLSyntaxError = None  # type: ignore[assignment]

        if XMLSyntaxError and isinstance(exc, XMLSyntaxError) and "not proper UTF-8" in str(exc):
            enc_attempts = [
                ("cp1252", "strict", False),
                ("latin-1", "strict", False),
                ("cp1252", "replace", True),
                ("latin-1", "replace", True),
            ]
            for enc, mode, use_recover in enc_attempts:
                try:
                    text = cleaned.decode(enc, errors=mode)
                    utf8_bytes = _clean_xml_bytes(text.encode("utf-8", errors="strict"))
                    if use_recover:
                        parser_recover = etree.XMLParser(recover=True)
                        root = etree.fromstring(utf8_bytes, parser=parser_recover)
                    else:
                        root = etree.fromstring(utf8_bytes)
                    if logger:
                        logger.warning(
                            "XML encoding fallback applied",
                            extra={
                                "file": file_name,
                                "fallback_encoding": enc,
                                "fallback_mode": mode,
                            },
                        )
                    return root, utf8_bytes
                except Exception:
                    continue
        raise FatturaPAParseError(
            f"XML non parsabile: file={file_name} parse_error={exc}"
        ) from exc


def _localname(tag: str | None) -> str:
    if not tag:
        return ""
    if "}" in tag:
        return tag.split("}", 1)[1]
    if ":" in tag:
        return tag.split(":", 1)[1]
    return tag


def _is_metadata_file(original_file_name: str, root) -> bool:
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

    if root_local in invoice_roots:
        return False
    if root_local in metadata_roots or root_local in notification_roots:
        return True
    if "metadato" in name_lower or "metadata" in name_lower:
        return True
    return True


def _get_text(root, xpath: str) -> Optional[str]:
    if root is None:
        return None
    res = root.xpath(xpath)
    if not res:
        return None
    node = res[0]
    if node is None or not getattr(node, "text", None):
        return None
    text = node.text.strip()
    return text or None


def _to_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _to_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if hasattr(value, "to_date"):
        try:
            return value.to_date()
        except Exception:
            return None
    try:
        year, month, day = str(value).split("-")
        return date(int(year), int(month), int(day))
    except Exception:
        return None


def _enum_to_str(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    if is_dataclass(value):
        return str(value)
    return str(value)
