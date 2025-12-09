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
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import List, Optional

from lxml import etree


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
    doc_status: str = "imported"
    payment_status: str = "unpaid"

    # Collezioni collegate
    lines: List[InvoiceLineDTO] = field(default_factory=list)
    vat_summaries: List[VatSummaryDTO] = field(default_factory=list)
    payments: List[PaymentDTO] = field(default_factory=list)


# =========================
#  Eccezioni specifiche
# =========================


class FatturaPAParseError(Exception):
    """Errore generico durante il parsing di una fattura XML."""


class P7MExtractionError(FatturaPAParseError):
    """Errore durante l'estrazione dell'XML da un file P7M."""


# =========================
#  Funzione principale di parsing
# =========================


def parse_invoice_xml(path: str | Path) -> InvoiceDTO:
    """
    Parsea un file XML FatturaPA e restituisce un InvoiceDTO.
    
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
        
        # Scrivi XML temporaneo per il parsing con lxml
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.xml', delete=False) as tmp:
            tmp.write(xml_content)
            tmp_path = tmp.name
        
        try:
            return _parse_xml_file(Path(tmp_path), original_file_name=file_path.name)
        finally:
            # Cleanup file temporaneo
            Path(tmp_path).unlink(missing_ok=True)
    
    # File XML normale
    return _parse_xml_file(file_path, original_file_name=file_path.name)


def _parse_xml_file(xml_path: Path, original_file_name: str) -> InvoiceDTO:
    """
    Parsing effettivo del file XML.
    
    :param xml_path: percorso del file XML da parsare
    :param original_file_name: nome originale del file (usato nel DTO)
    """
    try:
        # Usa parser con recover=True per gestire XML malformati
        parser = etree.XMLParser(recover=True, encoding='utf-8')
        tree = etree.parse(str(xml_path), parser)
    except (OSError, etree.XMLSyntaxError) as exc:
        raise FatturaPAParseError(f"Errore nel parsing XML: {exc}") from exc

    root = tree.getroot()

    # Prendiamo il primo FatturaElettronicaBody disponibile
    body = _first(
        root,
        ".//*[local-name()='FatturaElettronicaBody']",
    )
    if body is None:
        # In alcune versioni, il body può coincidere con root o avere nomi leggermente diversi,
        # ma almeno un DatiGeneraliDocumento deve essere presente.
        body = root

    # Supplier
    supplier_dto = _parse_supplier(root)

    # Testata fattura
    (
        invoice_number,
        invoice_series,
        invoice_date,
        currency,
        total_gross_amount,
    ) = _parse_invoice_header(body)

    # Righe fattura
    lines_dto = _parse_invoice_lines(body)

    # Riepilogo IVA
    vat_summaries_dto, total_taxable, total_vat = _parse_vat_summaries(body)

    # Dati pagamento
    payments_dto, main_due_date = _parse_payments(body)

    # Costruzione DTO principale
    invoice_dto = InvoiceDTO(
        supplier=supplier_dto,
        invoice_number=invoice_number,
        invoice_series=invoice_series,
        invoice_date=invoice_date,
        registration_date=None,  # per ora non presente nell'XML standard
        currency=currency or "EUR",
        total_taxable_amount=total_taxable,
        total_vat_amount=total_vat,
        total_gross_amount=total_gross_amount or (
            (total_taxable or Decimal("0")) + (total_vat or Decimal("0"))
            if (total_taxable is not None and total_vat is not None)
            else None
        ),
        due_date=main_due_date,
        file_name=original_file_name,
        file_hash=None,  # opzionale: può essere calcolato dal servizio di import
        doc_status="imported",
        payment_status="unpaid",
        lines=lines_dto,
        vat_summaries=vat_summaries_dto,
        payments=payments_dto,
    )

    return invoice_dto


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
    try:
        # Leggi il contenuto Base64 del P7M
        with open(p7m_path, 'r', encoding='utf-8', errors='ignore') as f:
            b64_data = f.read()
        
        # Rimuovi spazi e newline
        b64_clean = ''.join(b64_data.split())
        
        # Aggiungi padding se necessario
        missing_padding = len(b64_clean) % 4
        if missing_padding:
            b64_clean += '=' * (4 - missing_padding)
        
        # Decodifica Base64
        decoded = base64.b64decode(b64_clean)
        
        # Cerca l'inizio dell'XML nel binario decodificato
        xml_start = _find_xml_start(decoded)
        
        if xml_start < 0:
            raise P7MExtractionError(
                f"Contenuto XML non trovato nel file P7M: {p7m_path}"
            )
        
        # Cerca la fine dell'XML
        xml_end = _find_xml_end(decoded, xml_start)
        
        if xml_end <= xml_start:
            raise P7MExtractionError(
                f"Fine XML non trovata nel file P7M: {p7m_path}"
            )
        
        # Estrai il contenuto XML
        xml_content = decoded[xml_start:xml_end]
        
        # Pulisci caratteri invalidi XML
        xml_content = _clean_xml_bytes(xml_content)
        
        return xml_content
        
    except base64.binascii.Error as exc:
        raise P7MExtractionError(
            f"Errore decodifica Base64 del file P7M: {exc}"
        ) from exc
    except Exception as exc:
        raise P7MExtractionError(
            f"Errore durante l'estrazione XML da P7M: {exc}"
        ) from exc


def _clean_xml_bytes(data: bytes) -> bytes:
    """
    Rimuove caratteri invalidi XML dal contenuto binario.
    
    XML valido consente solo:
    - caratteri ASCII stampabili
    - tab, newline, carriage return
    - caratteri Unicode validi
    
    Rimuove bytes che causano errori di parsing, inclusi bytes corrotti
    all'interno dei tag XML.
    """
    # Decodifica con encoding windows-1252 (usato in molti XML FatturaPA)
    try:
        text = data.decode('windows-1252', errors='ignore')
    except:
        text = data.decode('utf-8', errors='ignore')
    
    # Rimuovi caratteri di controllo non validi per XML
    # XML valido: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    cleaned = []
    in_tag = False
    
    for char in text:
        code = ord(char)
        
        # Traccia se siamo dentro un tag
        if char == '<':
            in_tag = True
            cleaned.append(char)
        elif char == '>':
            in_tag = False
            cleaned.append(char)
        # Se siamo dentro un tag, sii più restrittivo: accetta solo ASCII stampabili + spazi
        elif in_tag:
            if (0x20 <= code <= 0x7E) or code == 0x9:  # ASCII stampabile + tab
                cleaned.append(char)
            # Skip tutti gli altri caratteri dentro i tag
        # Fuori dai tag, accetta caratteri XML validi
        elif (code == 0x9 or code == 0xA or code == 0xD or 
              (0x20 <= code <= 0xD7FF) or 
              (0xE000 <= code <= 0xFFFD) or
              (0x10000 <= code <= 0x10FFFF)):
            cleaned.append(char)
    
    # Ricodifica in bytes
    return ''.join(cleaned).encode('utf-8')


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


def _parse_supplier(root) -> SupplierDTO:
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
    name = _get_text(
        supplier_node, ".//*[local-name()='Denominazione']"
    ) or _get_text(
        supplier_node,
        ".//*[local-name()='Nome']"
        "|.//*[local-name()='Cognome']",
    )

    # IVA e CF
    vat_number = _get_text(
        supplier_node,
        ".//*[local-name()='IdFiscaleIVA']/*[local-name()='IdCodice']",
    )
    fiscal_code = _get_text(supplier_node, ".//*[local-name()='CodiceFiscale']")

    # Codice destinatario / SDI
    sdi_code = _get_text(
        root,
        ".//*[local-name()='DatiTrasmissione']/*[local-name()='CodiceDestinatario']",
    )

    # PEC destinatario
    pec_email = _get_text(
        root,
        ".//*[local-name()='DatiTrasmissione']/*[local-name()='PECDestinatario']",
    )

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

    return SupplierDTO(
        name=name,
        vat_number=vat_number,
        fiscal_code=fiscal_code,
        sdi_code=sdi_code,
        pec_email=pec_email,
        address=address,
        postal_code=postal_code,
        city=city,
        province=province,
        country=country,
    )


# ---------- Testata fattura ----------


def _parse_invoice_header(body) -> tuple[
    Optional[str], Optional[str], Optional[date], Optional[str], Optional[Decimal]
]:
    """
    Estrae i dati principali del documento (DatiGeneraliDocumento):

    - Numero
    - Divisa
    - Data
    - ImportoTotaleDocumento
    """
    dg_node = _first(body, ".//*[local-name()='DatiGeneraliDocumento']")

    if dg_node is None:
        # Questo caso non dovrebbe verificarsi in FatturaPA valida,
        # ma evitiamo di esplodere.
        return None, None, None, None, None

    invoice_number = _get_text(dg_node, ".//*[local-name()='Numero']")
    invoice_date_str = _get_text(dg_node, ".//*[local-name()='Data']")
    invoice_date = _to_date(invoice_date_str)

    currency = _get_text(dg_node, ".//*[local-name()='Divisa']")
    total_gross_str = _get_text(
        dg_node, ".//*[local-name()='ImportoTotaleDocumento']"
    )
    total_gross = _to_decimal(total_gross_str)

    # Serie (non sempre presente esplicita; talvolta è incorporata nel Numero)
    invoice_series = None  # Manteniamo questo campo per possibili estensioni future

    return invoice_number, invoice_series, invoice_date, currency, total_gross


# ---------- DettaglioLinee ----------


def _parse_invoice_lines(body) -> List[InvoiceLineDTO]:
    """
    Estrae le righe fattura (DettaglioLinee).

    Restituisce una lista di InvoiceLineDTO.
    """
    lines: List[InvoiceLineDTO] = []

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