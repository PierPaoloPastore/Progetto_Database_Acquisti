from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from xsdata.models.datatype import XmlDate


@dataclass
class AllegatiType:
    """
    Blocco relativo ai dati di eventuali allegati.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    nome_attachment: Optional[str] = field(
        default=None,
        metadata={
            "name": "NomeAttachment",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    algoritmo_compressione: Optional[str] = field(
        default=None,
        metadata={
            "name": "AlgoritmoCompressione",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,10})',
        }
    )
    formato_attachment: Optional[str] = field(
        default=None,
        metadata={
            "name": "FormatoAttachment",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,10})',
        }
    )
    descrizione_attachment: Optional[str] = field(
        default=None,
        metadata={
            "name": "DescrizioneAttachment",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,100}',
        }
    )
    attachment: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "Attachment",
            "type": "Element",
            "namespace": "",
            "required": True,
            "format": "base64",
        }
    )
class BolloVirtualeType(Enum):
    SI = 'SI'
@dataclass
class DatiFatturaRettificataType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    numero_fr: Optional[str] = field(
        default=None,
        metadata={
            "name": "NumeroFR",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    data_fr: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataFR",
            "type": "Element",
            "namespace": "",
            "required": True,
            "min_inclusive": XmlDate(1970, 1, 1),
        }
    )
    elementi_rettificati: Optional[str] = field(
        default=None,
        metadata={
            "name": "ElementiRettificati",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,1000}',
        }
    )
@dataclass
class DatiIvatype:
    class Meta:
        name = "DatiIVAType"
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    imposta: Optional[str] = field(
        default=None,
        metadata={
            "name": "Imposta",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    aliquota: Optional[str] = field(
        default=None,
        metadata={
            "name": "Aliquota",
            "type": "Element",
            "namespace": "",
            "max_inclusive": "100.00",
            "pattern": r'[0-9]{1,3}\.[0-9]{2}',
        }
    )
class FormatoTrasmissioneType(Enum):
    """
    :cvar FSM10: Fattura verso privati semplificata
    """
    FSM10 = 'FSM10'
@dataclass
class IdFiscaleType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    id_paese: Optional[str] = field(
        default=None,
        metadata={
            "name": "IdPaese",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[A-Z]{2}',
        }
    )
    id_codice: Optional[str] = field(
        default=None,
        metadata={
            "name": "IdCodice",
            "type": "Element",
            "namespace": "",
            "required": True,
            "min_length": 1,
            "max_length": 28,
        }
    )
@dataclass
class IndirizzoType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    indirizzo: Optional[str] = field(
        default=None,
        metadata={
            "name": "Indirizzo",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    numero_civico: Optional[str] = field(
        default=None,
        metadata={
            "name": "NumeroCivico",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,8})',
        }
    )
    cap: Optional[str] = field(
        default=None,
        metadata={
            "name": "CAP",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[0-9][0-9][0-9][0-9][0-9]',
        }
    )
    comune: Optional[str] = field(
        default=None,
        metadata={
            "name": "Comune",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    provincia: Optional[str] = field(
        default=None,
        metadata={
            "name": "Provincia",
            "type": "Element",
            "namespace": "",
            "pattern": r'[A-Z]{2}',
        }
    )
    nazione: str = field(
        default='IT',
        metadata={
            "name": "Nazione",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[A-Z]{2}',
        }
    )
class NaturaType(Enum):
    """
    :cvar N1: Escluse ex. art. 15 del D.P.R. 633/1972
    :cvar N2: Non soggette
    :cvar N2_1: Non soggette ad IVA ai sensi degli artt. da 7 a
        7-septies del DPR 633/72
    :cvar N2_2: Non soggette - altri casi
    :cvar N3: Non imponibili
    :cvar N3_1: Non Imponibili - esportazioni
    :cvar N3_2: Non Imponibili - cessioni intracomunitarie
    :cvar N3_3: Non Imponibili - cessioni verso San Marino
    :cvar N3_4: Non Imponibili - operazioni assimilate alle cessioni
        all'esportazione
    :cvar N3_5: Non Imponibili - a seguito di dichiarazioni d'intento
    :cvar N3_6: Non Imponibili - altre operazioni che non concorrono
        alla formazione del plafond
    :cvar N4: Esenti
    :cvar N5: Regime del margine/IVA non esposta in fattura
    """
    N1 = 'N1'
    N2 = 'N2'
    N2_1 = 'N2.1'
    N2_2 = 'N2.2'
    N3 = 'N3'
    N3_1 = 'N3.1'
    N3_2 = 'N3.2'
    N3_3 = 'N3.3'
    N3_4 = 'N3.4'
    N3_5 = 'N3.5'
    N3_6 = 'N3.6'
    N4 = 'N4'
    N5 = 'N5'
class RegimeFiscaleType(Enum):
    """
    :cvar RF01: Regime ordinario
    :cvar RF02: Regime dei contribuenti minimi (art. 1,c.96-117, L.
        244/2007)
    :cvar RF04: Agricoltura e attività connesse e pesca (artt. 34 e
        34-bis, D.P.R. 633/1972)
    :cvar RF05: Vendita sali e tabacchi (art. 74, c.1, D.P.R. 633/1972)
    :cvar RF06: Commercio dei fiammiferi (art. 74, c.1, D.P.R. 633/1972)
    :cvar RF07: Editoria (art. 74, c.1, D.P.R. 633/1972)
    :cvar RF08: Gestione di servizi di telefonia pubblica (art. 74, c.1,
        D.P.R. 633/1972)
    :cvar RF09: Rivendita di documenti di trasporto pubblico e di sosta
        (art. 74, c.1, D.P.R. 633/1972)
    :cvar RF10: Intrattenimenti, giochi e altre attività    di cui alla
        tariffa allegata al D.P.R. 640/72 (art. 74, c.6, D.P.R.
        633/1972)
    :cvar RF11: Agenzie di viaggi e turismo (art. 74-ter, D.P.R.
        633/1972)
    :cvar RF12: Agriturismo (art. 5, c.2, L. 413/1991)
    :cvar RF13: Vendite a domicilio (art. 25-bis, c.6, D.P.R. 600/1973)
    :cvar RF14: Rivendita di beni usati, di oggetti d’arte,
        d’antiquariato o da collezione (art.    36, D.L. 41/1995)
    :cvar RF15: Agenzie di vendite all’asta di oggetti d’arte,
        antiquariato o da collezione (art. 40-bis, D.L. 41/1995)
    :cvar RF16: IVA per cassa P.A. (art. 6, c.5, D.P.R. 633/1972)
    :cvar RF17: IVA per cassa (art. 32-bis, D.L. 83/2012)
    :cvar RF18: Altro
    :cvar RF19: Regime forfettario
    :cvar RF20: Regime transfrontaliero di Franchigia IVA (Direttiva UE
        2020/285)
    """
    RF01 = 'RF01'
    RF02 = 'RF02'
    RF04 = 'RF04'
    RF05 = 'RF05'
    RF06 = 'RF06'
    RF07 = 'RF07'
    RF08 = 'RF08'
    RF09 = 'RF09'
    RF10 = 'RF10'
    RF11 = 'RF11'
    RF12 = 'RF12'
    RF13 = 'RF13'
    RF14 = 'RF14'
    RF15 = 'RF15'
    RF16 = 'RF16'
    RF17 = 'RF17'
    RF18 = 'RF18'
    RF19 = 'RF19'
    RF20 = 'RF20'
class SocioUnicoType(Enum):
    """
    :cvar SU: socio unico
    :cvar SM: più soci
    """
    SU = 'SU'
    SM = 'SM'
class SoggettoEmittenteType(Enum):
    """
    :cvar CC: Cessionario / Committente
    :cvar TZ: Terzo
    """
    CC = 'CC'
    TZ = 'TZ'
class StatoLiquidazioneType(Enum):
    """
    :cvar LS: in liquidazione
    :cvar LN: non in liquidazione
    """
    LS = 'LS'
    LN = 'LN'
class TipoDocumentoType(Enum):
    """
    :cvar TD07: Fattura semplificata
    :cvar TD08: Nota di credito semplificata
    :cvar TD09: Nota di debito semplificata
    """
    TD07 = 'TD07'
    TD08 = 'TD08'
    TD09 = 'TD09'
@dataclass
class CanonicalizationMethodType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    algorithm: Optional[str] = field(
        default=None,
        metadata={
            "name": "Algorithm",
            "type": "Attribute",
            "required": True,
        }
    )
    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
        }
    )
@dataclass
class DsakeyValueType:
    class Meta:
        name = "DSAKeyValueType"
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    p: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "P",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "format": "base64",
        }
    )
    q: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "Q",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "format": "base64",
        }
    )
    g: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "G",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "format": "base64",
        }
    )
    y: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "Y",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
            "format": "base64",
        }
    )
    j: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "J",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "format": "base64",
        }
    )
    seed: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "Seed",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "format": "base64",
        }
    )
    pgen_counter: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "PgenCounter",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "format": "base64",
        }
    )
@dataclass
class DigestMethodType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    algorithm: Optional[str] = field(
        default=None,
        metadata={
            "name": "Algorithm",
            "type": "Attribute",
            "required": True,
        }
    )
    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
        }
    )
@dataclass
class DigestValue:
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"

    value: Optional[bytes] = field(
        default=None,
        metadata={
            "required": True,
            "format": "base64",
        }
    )
@dataclass
class KeyName:
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"

    value: str = field(
        default='',
        metadata={
            "required": True,
        }
    )
@dataclass
class MgmtData:
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"

    value: str = field(
        default='',
        metadata={
            "required": True,
        }
    )
@dataclass
class ObjectType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
    mime_type: Optional[str] = field(
        default=None,
        metadata={
            "name": "MimeType",
            "type": "Attribute",
        }
    )
    encoding: Optional[str] = field(
        default=None,
        metadata={
            "name": "Encoding",
            "type": "Attribute",
        }
    )
    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
        }
    )
@dataclass
class PgpdataType:
    class Meta:
        name = "PGPDataType"
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    pgpkey_id: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "PGPKeyID",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
            "format": "base64",
        }
    )
    pgpkey_packet: list[bytes] = field(
        default_factory=list,
        metadata={
            "name": "PGPKeyPacket",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "max_occurs": 2,
            "format": "base64",
        }
    )
    other_element: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##other",
        }
    )
@dataclass
class RsakeyValueType:
    class Meta:
        name = "RSAKeyValueType"
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    modulus: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "Modulus",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
            "format": "base64",
        }
    )
    exponent: Optional[bytes] = field(
        default=None,
        metadata={
            "name": "Exponent",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
            "format": "base64",
        }
    )
@dataclass
class SpkidataType:
    class Meta:
        name = "SPKIDataType"
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    spkisexp: list[bytes] = field(
        default_factory=list,
        metadata={
            "name": "SPKISexp",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "min_occurs": 1,
            "sequence": 1,
            "format": "base64",
        }
    )
    other_element: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##other",
            "sequence": 1,
        }
    )
@dataclass
class SignatureMethodType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    algorithm: Optional[str] = field(
        default=None,
        metadata={
            "name": "Algorithm",
            "type": "Attribute",
            "required": True,
        }
    )
    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
            "choices": (
                {
                    "name": "HMACOutputLength",
                    "type": int,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
            ),
        }
    )
@dataclass
class SignaturePropertyType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    target: Optional[str] = field(
        default=None,
        metadata={
            "name": "Target",
            "type": "Attribute",
            "required": True,
        }
    )
    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
        }
    )
@dataclass
class SignatureValueType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    value: Optional[bytes] = field(
        default=None,
        metadata={
            "required": True,
            "format": "base64",
        }
    )
    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
@dataclass
class TransformType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    algorithm: Optional[str] = field(
        default=None,
        metadata={
            "name": "Algorithm",
            "type": "Attribute",
            "required": True,
        }
    )
    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
            "choices": (
                {
                    "name": "XPath",
                    "type": str,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
            ),
        }
    )
@dataclass
class X509IssuerSerialType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    x509_issuer_name: Optional[str] = field(
        default=None,
        metadata={
            "name": "X509IssuerName",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
        }
    )
    x509_serial_number: Optional[int] = field(
        default=None,
        metadata={
            "name": "X509SerialNumber",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
        }
    )
@dataclass
class DatiBeniServiziType:
    """
    Blocco relativo ai dati di Beni Servizi della Fattura   Elettronica.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    descrizione: Optional[str] = field(
        default=None,
        metadata={
            "name": "Descrizione",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,1000}',
        }
    )
    importo: Optional[str] = field(
        default=None,
        metadata={
            "name": "Importo",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    dati_iva: Optional[DatiIvatype] = field(
        default=None,
        metadata={
            "name": "DatiIVA",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    natura: Optional[NaturaType] = field(
        default=None,
        metadata={
            "name": "Natura",
            "type": "Element",
            "namespace": "",
        }
    )
    riferimento_normativo: Optional[str] = field(
        default=None,
        metadata={
            "name": "RiferimentoNormativo",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,100}',
        }
    )
@dataclass
class DatiGeneraliDocumentoType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    tipo_documento: Optional[TipoDocumentoType] = field(
        default=None,
        metadata={
            "name": "TipoDocumento",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    divisa: Optional[str] = field(
        default=None,
        metadata={
            "name": "Divisa",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[A-Z]{3}',
        }
    )
    data: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "Data",
            "type": "Element",
            "namespace": "",
            "required": True,
            "min_inclusive": XmlDate(1970, 1, 1),
        }
    )
    numero: Optional[str] = field(
        default=None,
        metadata={
            "name": "Numero",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    bollo_virtuale: Optional[BolloVirtualeType] = field(
        default=None,
        metadata={
            "name": "BolloVirtuale",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class DatiTrasmissioneType:
    """
    Blocco relativo ai dati di trasmissione della Fattura Elettronica.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    id_trasmittente: Optional[IdFiscaleType] = field(
        default=None,
        metadata={
            "name": "IdTrasmittente",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    progressivo_invio: Optional[str] = field(
        default=None,
        metadata={
            "name": "ProgressivoInvio",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,10})',
        }
    )
    formato_trasmissione: Optional[FormatoTrasmissioneType] = field(
        default=None,
        metadata={
            "name": "FormatoTrasmissione",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    codice_destinatario: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodiceDestinatario",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[A-Z0-9]{7}',
        }
    )
    pecdestinatario: Optional[str] = field(
        default=None,
        metadata={
            "name": "PECDestinatario",
            "type": "Element",
            "namespace": "",
            "max_length": 256,
            "pattern": r'([!#-\'*+/-9=?A-Z^-~-]+(\.[!#-\'*+/-9=?A-Z^-~-]+)*|"(\[\]!#-[^-~ \t]|(\\[\t -~]))+")@([!#-\'*+/-9=?A-Z^-~-]+(\.[!#-\'*+/-9=?A-Z^-~-]+)*|\[[\t -Z^-~]*\])',
        }
    )
@dataclass
class IdentificativiFiscaliType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    id_fiscale_iva: Optional[IdFiscaleType] = field(
        default=None,
        metadata={
            "name": "IdFiscaleIVA",
            "type": "Element",
            "namespace": "",
        }
    )
    codice_fiscale: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodiceFiscale",
            "type": "Element",
            "namespace": "",
            "pattern": r'[A-Z0-9]{11,16}',
        }
    )
@dataclass
class IscrizioneReatype:
    class Meta:
        name = "IscrizioneREAType"
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    ufficio: Optional[str] = field(
        default=None,
        metadata={
            "name": "Ufficio",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[A-Z]{2}',
        }
    )
    numero_rea: Optional[str] = field(
        default=None,
        metadata={
            "name": "NumeroREA",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    capitale_sociale: Optional[str] = field(
        default=None,
        metadata={
            "name": "CapitaleSociale",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    socio_unico: Optional[SocioUnicoType] = field(
        default=None,
        metadata={
            "name": "SocioUnico",
            "type": "Element",
            "namespace": "",
        }
    )
    stato_liquidazione: Optional[StatoLiquidazioneType] = field(
        default=None,
        metadata={
            "name": "StatoLiquidazione",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
@dataclass
class RappresentanteFiscaleType:
    """
    Blocco relativo ai dati del Rappresentante Fiscale.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    id_fiscale_iva: Optional[IdFiscaleType] = field(
        default=None,
        metadata={
            "name": "IdFiscaleIVA",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    denominazione: Optional[str] = field(
        default=None,
        metadata={
            "name": "Denominazione",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,80}',
        }
    )
    nome: Optional[str] = field(
        default=None,
        metadata={
            "name": "Nome",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    cognome: Optional[str] = field(
        default=None,
        metadata={
            "name": "Cognome",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
@dataclass
class CanonicalizationMethod(CanonicalizationMethodType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class DsakeyValue(DsakeyValueType):
    class Meta:
        name = "DSAKeyValue"
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class DigestMethod(DigestMethodType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class Object(ObjectType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class Pgpdata(PgpdataType):
    class Meta:
        name = "PGPData"
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class RsakeyValue(RsakeyValueType):
    class Meta:
        name = "RSAKeyValue"
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class Spkidata(SpkidataType):
    class Meta:
        name = "SPKIData"
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class SignatureMethod(SignatureMethodType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class SignatureProperty(SignaturePropertyType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class SignatureValue(SignatureValueType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class Transform(TransformType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class X509DataType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    x509_issuer_serial: list[X509IssuerSerialType] = field(
        default_factory=list,
        metadata={
            "name": "X509IssuerSerial",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "sequence": 1,
        }
    )
    x509_ski: list[bytes] = field(
        default_factory=list,
        metadata={
            "name": "X509SKI",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "sequence": 1,
            "format": "base64",
        }
    )
    x509_subject_name: list[str] = field(
        default_factory=list,
        metadata={
            "name": "X509SubjectName",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "sequence": 1,
        }
    )
    x509_certificate: list[bytes] = field(
        default_factory=list,
        metadata={
            "name": "X509Certificate",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "sequence": 1,
            "format": "base64",
        }
    )
    x509_crl: list[bytes] = field(
        default_factory=list,
        metadata={
            "name": "X509CRL",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "sequence": 1,
            "format": "base64",
        }
    )
    other_element: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##other",
            "sequence": 1,
        }
    )
@dataclass
class AltriDatiIdentificativiType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    denominazione: Optional[str] = field(
        default=None,
        metadata={
            "name": "Denominazione",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,80}',
        }
    )
    nome: Optional[str] = field(
        default=None,
        metadata={
            "name": "Nome",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    cognome: Optional[str] = field(
        default=None,
        metadata={
            "name": "Cognome",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    sede: Optional[IndirizzoType] = field(
        default=None,
        metadata={
            "name": "Sede",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    stabile_organizzazione: Optional[IndirizzoType] = field(
        default=None,
        metadata={
            "name": "StabileOrganizzazione",
            "type": "Element",
            "namespace": "",
        }
    )
    rappresentante_fiscale: Optional[RappresentanteFiscaleType] = field(
        default=None,
        metadata={
            "name": "RappresentanteFiscale",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class CedentePrestatoreType:
    """
    Blocco relativo ai dati del Cedente / Prestatore.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    id_fiscale_iva: Optional[IdFiscaleType] = field(
        default=None,
        metadata={
            "name": "IdFiscaleIVA",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    codice_fiscale: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodiceFiscale",
            "type": "Element",
            "namespace": "",
            "pattern": r'[A-Z0-9]{11,16}',
        }
    )
    denominazione: Optional[str] = field(
        default=None,
        metadata={
            "name": "Denominazione",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,80}',
        }
    )
    nome: Optional[str] = field(
        default=None,
        metadata={
            "name": "Nome",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    cognome: Optional[str] = field(
        default=None,
        metadata={
            "name": "Cognome",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    sede: Optional[IndirizzoType] = field(
        default=None,
        metadata={
            "name": "Sede",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    stabile_organizzazione: Optional[IndirizzoType] = field(
        default=None,
        metadata={
            "name": "StabileOrganizzazione",
            "type": "Element",
            "namespace": "",
        }
    )
    rappresentante_fiscale: Optional[RappresentanteFiscaleType] = field(
        default=None,
        metadata={
            "name": "RappresentanteFiscale",
            "type": "Element",
            "namespace": "",
        }
    )
    iscrizione_rea: Optional[IscrizioneReatype] = field(
        default=None,
        metadata={
            "name": "IscrizioneREA",
            "type": "Element",
            "namespace": "",
        }
    )
    regime_fiscale: Optional[RegimeFiscaleType] = field(
        default=None,
        metadata={
            "name": "RegimeFiscale",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
@dataclass
class DatiGeneraliType:
    """
    Blocco relativo ai Dati Generali della Fattura Elettronica.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    dati_generali_documento: Optional[DatiGeneraliDocumentoType] = field(
        default=None,
        metadata={
            "name": "DatiGeneraliDocumento",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    dati_fattura_rettificata: Optional[DatiFatturaRettificataType] = field(
        default=None,
        metadata={
            "name": "DatiFatturaRettificata",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class KeyValueType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
            "choices": (
                {
                    "name": "DSAKeyValue",
                    "type": DsakeyValue,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
                {
                    "name": "RSAKeyValue",
                    "type": RsakeyValue,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
            ),
        }
    )
@dataclass
class SignaturePropertiesType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    signature_property: list[SignatureProperty] = field(
        default_factory=list,
        metadata={
            "name": "SignatureProperty",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "min_occurs": 1,
        }
    )
    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
@dataclass
class TransformsType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    transform: list[Transform] = field(
        default_factory=list,
        metadata={
            "name": "Transform",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "min_occurs": 1,
        }
    )
@dataclass
class X509Data(X509DataType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class CessionarioCommittenteType:
    """
    Blocco relativo ai dati del Cessionario / Committente.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    identificativi_fiscali: Optional[IdentificativiFiscaliType] = field(
        default=None,
        metadata={
            "name": "IdentificativiFiscali",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    altri_dati_identificativi: Optional[AltriDatiIdentificativiType] = field(
        default=None,
        metadata={
            "name": "AltriDatiIdentificativi",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class FatturaElettronicaBodyType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    dati_generali: Optional[DatiGeneraliType] = field(
        default=None,
        metadata={
            "name": "DatiGenerali",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    dati_beni_servizi: list[DatiBeniServiziType] = field(
        default_factory=list,
        metadata={
            "name": "DatiBeniServizi",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        }
    )
    allegati: list[AllegatiType] = field(
        default_factory=list,
        metadata={
            "name": "Allegati",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class KeyValue(KeyValueType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class SignatureProperties(SignaturePropertiesType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class Transforms(TransformsType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class FatturaElettronicaHeaderType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    dati_trasmissione: Optional[DatiTrasmissioneType] = field(
        default=None,
        metadata={
            "name": "DatiTrasmissione",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    cedente_prestatore: Optional[CedentePrestatoreType] = field(
        default=None,
        metadata={
            "name": "CedentePrestatore",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    cessionario_committente: Optional[CessionarioCommittenteType] = field(
        default=None,
        metadata={
            "name": "CessionarioCommittente",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    soggetto_emittente: Optional[SoggettoEmittenteType] = field(
        default=None,
        metadata={
            "name": "SoggettoEmittente",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class ReferenceType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    transforms: Optional[Transforms] = field(
        default=None,
        metadata={
            "name": "Transforms",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
        }
    )
    digest_method: Optional[DigestMethod] = field(
        default=None,
        metadata={
            "name": "DigestMethod",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
        }
    )
    digest_value: Optional[DigestValue] = field(
        default=None,
        metadata={
            "name": "DigestValue",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
        }
    )
    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
    uri: Optional[str] = field(
        default=None,
        metadata={
            "name": "URI",
            "type": "Attribute",
        }
    )
    type_value: Optional[str] = field(
        default=None,
        metadata={
            "name": "Type",
            "type": "Attribute",
        }
    )
@dataclass
class RetrievalMethodType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    transforms: Optional[Transforms] = field(
        default=None,
        metadata={
            "name": "Transforms",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
        }
    )
    uri: Optional[str] = field(
        default=None,
        metadata={
            "name": "URI",
            "type": "Attribute",
        }
    )
    type_value: Optional[str] = field(
        default=None,
        metadata={
            "name": "Type",
            "type": "Attribute",
        }
    )
@dataclass
class Reference(ReferenceType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class RetrievalMethod(RetrievalMethodType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class KeyInfoType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
    content: list[object] = field(
        default_factory=list,
        metadata={
            "type": "Wildcard",
            "namespace": "##any",
            "mixed": True,
            "choices": (
                {
                    "name": "KeyName",
                    "type": KeyName,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
                {
                    "name": "KeyValue",
                    "type": KeyValue,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
                {
                    "name": "RetrievalMethod",
                    "type": RetrievalMethod,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
                {
                    "name": "X509Data",
                    "type": X509Data,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
                {
                    "name": "PGPData",
                    "type": Pgpdata,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
                {
                    "name": "SPKIData",
                    "type": Spkidata,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
                {
                    "name": "MgmtData",
                    "type": MgmtData,
                    "namespace": "http://www.w3.org/2000/09/xmldsig#",
                },
            ),
        }
    )
@dataclass
class ManifestType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    reference: list[Reference] = field(
        default_factory=list,
        metadata={
            "name": "Reference",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "min_occurs": 1,
        }
    )
    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
@dataclass
class SignedInfoType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    canonicalization_method: Optional[CanonicalizationMethod] = field(
        default=None,
        metadata={
            "name": "CanonicalizationMethod",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
        }
    )
    signature_method: Optional[SignatureMethod] = field(
        default=None,
        metadata={
            "name": "SignatureMethod",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
        }
    )
    reference: list[Reference] = field(
        default_factory=list,
        metadata={
            "name": "Reference",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "min_occurs": 1,
        }
    )
    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
@dataclass
class KeyInfo(KeyInfoType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class Manifest(ManifestType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class SignedInfo(SignedInfoType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class SignatureType:
    class Meta:
        target_namespace = "http://www.w3.org/2000/09/xmldsig#"

    signed_info: Optional[SignedInfo] = field(
        default=None,
        metadata={
            "name": "SignedInfo",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
        }
    )
    signature_value: Optional[SignatureValue] = field(
        default=None,
        metadata={
            "name": "SignatureValue",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
            "required": True,
        }
    )
    key_info: Optional[KeyInfo] = field(
        default=None,
        metadata={
            "name": "KeyInfo",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
        }
    )
    object_value: list[Object] = field(
        default_factory=list,
        metadata={
            "name": "Object",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
        }
    )
    id: Optional[str] = field(
        default=None,
        metadata={
            "name": "Id",
            "type": "Attribute",
        }
    )
@dataclass
class Signature(SignatureType):
    class Meta:
        namespace = "http://www.w3.org/2000/09/xmldsig#"
@dataclass
class FatturaElettronicaType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"

    fattura_elettronica_header: Optional[FatturaElettronicaHeaderType] = field(
        default=None,
        metadata={
            "name": "FatturaElettronicaHeader",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    fattura_elettronica_body: list[FatturaElettronicaBodyType] = field(
        default_factory=list,
        metadata={
            "name": "FatturaElettronicaBody",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        }
    )
    signature: Optional[Signature] = field(
        default=None,
        metadata={
            "name": "Signature",
            "type": "Element",
            "namespace": "http://www.w3.org/2000/09/xmldsig#",
        }
    )
    versione: Optional[FormatoTrasmissioneType] = field(
        default=None,
        metadata={
            "type": "Attribute",
            "required": True,
        }
    )
    sistema_emittente: Optional[str] = field(
        default=None,
        metadata={
            "name": "SistemaEmittente",
            "type": "Attribute",
            "pattern": r'(\p{IsBasicLatin}{1,10})',
        }
    )
@dataclass
class FatturaElettronicaSemplificata(FatturaElettronicaType):
    """
    XML schema fatture destinate a privati in forma semplificata 1.0.2.
    """
    class Meta:
        namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.0"