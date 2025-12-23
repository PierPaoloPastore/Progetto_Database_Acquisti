from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from xsdata.models.datatype import XmlDate, XmlDateTime


@dataclass
class AllegatiType:
    """
    Blocco relativo ai dati di eventuali allegati.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
@dataclass
class AltriDatiGestionaliType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    tipo_dato: Optional[str] = field(
        default=None,
        metadata={
            "name": "TipoDato",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,10})',
        }
    )
    riferimento_testo: Optional[str] = field(
        default=None,
        metadata={
            "name": "RiferimentoTesto",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    riferimento_numero: Optional[str] = field(
        default=None,
        metadata={
            "name": "RiferimentoNumero",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2,8}',
        }
    )
    riferimento_data: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "RiferimentoData",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class AnagraficaType:
    """
    Il campo Denominazione è in alternativa ai campi Nome e Cognome.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
    titolo: Optional[str] = field(
        default=None,
        metadata={
            "name": "Titolo",
            "type": "Element",
            "namespace": "",
            "white_space": "collapse",
            "pattern": r'(\p{IsBasicLatin}{2,10})',
        }
    )
    cod_eori: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodEORI",
            "type": "Element",
            "namespace": "",
            "min_length": 13,
            "max_length": 17,
        }
    )
class Art73Type(Enum):
    """
    :cvar SI: SI = Documento emesso secondo modalità e termini stabiliti
        con DM ai sensi dell'art. 73 DPR 633/72
    """
    SI = 'SI'
class BolloVirtualeType(Enum):
    SI = 'SI'
class CausalePagamentoType(Enum):
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'
    E = 'E'
    G = 'G'
    H = 'H'
    I = 'I'
    L = 'L'
    M = 'M'
    N = 'N'
    O = 'O'
    P = 'P'
    Q = 'Q'
    R = 'R'
    S = 'S'
    T = 'T'
    U = 'U'
    V = 'V'
    W = 'W'
    X = 'X'
    Y = 'Y'
    Z = 'Z'
    L1 = 'L1'
    M1 = 'M1'
    M2 = 'M2'
    O1 = 'O1'
    V1 = 'V1'
    ZO = 'ZO'
@dataclass
class CodiceArticoloType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    codice_tipo: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodiceTipo",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,35})',
        }
    )
    codice_valore: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodiceValore",
            "type": "Element",
            "namespace": "",
            "required": True,
            "min_length": 1,
            "max_length": 35,
        }
    )
class CondizioniPagamentoType(Enum):
    """
    :cvar TP01: pagamento a rate
    :cvar TP02: pagamento completo
    :cvar TP03: anticipo
    """
    TP01 = 'TP01'
    TP02 = 'TP02'
    TP03 = 'TP03'
@dataclass
class ContattiTrasmittenteType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    telefono: Optional[str] = field(
        default=None,
        metadata={
            "name": "Telefono",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{5,12})',
        }
    )
    email: Optional[str] = field(
        default=None,
        metadata={
            "name": "Email",
            "type": "Element",
            "namespace": "",
            "min_length": 7,
            "max_length": 256,
            "pattern": r'.+@.+[.]+.+',
        }
    )
@dataclass
class ContattiType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    telefono: Optional[str] = field(
        default=None,
        metadata={
            "name": "Telefono",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{5,12})',
        }
    )
    fax: Optional[str] = field(
        default=None,
        metadata={
            "name": "Fax",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{5,12})',
        }
    )
    email: Optional[str] = field(
        default=None,
        metadata={
            "name": "Email",
            "type": "Element",
            "namespace": "",
            "min_length": 7,
            "max_length": 256,
            "pattern": r'.+@.+[.]+.+',
        }
    )
@dataclass
class DatiDdttype:
    class Meta:
        name = "DatiDDTType"
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    numero_ddt: Optional[str] = field(
        default=None,
        metadata={
            "name": "NumeroDDT",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    data_ddt: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataDDT",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    riferimento_numero_linea: list[int] = field(
        default_factory=list,
        metadata={
            "name": "RiferimentoNumeroLinea",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 1,
            "max_inclusive": 9999,
        }
    )
@dataclass
class DatiDocumentiCorrelatiType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    riferimento_numero_linea: list[int] = field(
        default_factory=list,
        metadata={
            "name": "RiferimentoNumeroLinea",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 1,
            "max_inclusive": 9999,
        }
    )
    id_documento: Optional[str] = field(
        default=None,
        metadata={
            "name": "IdDocumento",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    data: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "Data",
            "type": "Element",
            "namespace": "",
        }
    )
    num_item: Optional[str] = field(
        default=None,
        metadata={
            "name": "NumItem",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    codice_commessa_convenzione: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodiceCommessaConvenzione",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,100}',
        }
    )
    codice_cup: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodiceCUP",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,15})',
        }
    )
    codice_cig: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodiceCIG",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,15})',
        }
    )
@dataclass
class DatiSaltype:
    class Meta:
        name = "DatiSALType"
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    riferimento_fase: Optional[int] = field(
        default=None,
        metadata={
            "name": "RiferimentoFase",
            "type": "Element",
            "namespace": "",
            "required": True,
            "min_inclusive": 1,
            "max_inclusive": 999,
        }
    )
@dataclass
class DatiVeicoliType:
    """Blocco relativo ai dati dei Veicoli della Fattura Elettronica (da indicare
    nei casi di cessioni tra Paesi membri di mezzi di trasporto nuovi, in base
    all'art.

    38, comma 4 del dl 331 del 1993)
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    data: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "Data",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    totale_percorso: Optional[str] = field(
        default=None,
        metadata={
            "name": "TotalePercorso",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,15})',
        }
    )
class EsigibilitaIvatype(Enum):
    """
    :cvar D: esigibilità differita
    :cvar I: esigibilità immediata
    :cvar S: scissione dei pagamenti
    """
    D = 'D'
    I = 'I'
    S = 'S'
@dataclass
class FatturaPrincipaleType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    numero_fattura_principale: Optional[str] = field(
        default=None,
        metadata={
            "name": "NumeroFatturaPrincipale",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    data_fattura_principale: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataFatturaPrincipale",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
class FormatoTrasmissioneType(Enum):
    """
    :cvar FPA12: Fattura verso PA
    :cvar FPR12: Fattura verso privati
    """
    FPA12 = 'FPA12'
    FPR12 = 'FPR12'
@dataclass
class IdFiscaleType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
class ModalitaPagamentoType(Enum):
    """
    :cvar MP01: contanti
    :cvar MP02: assegno
    :cvar MP03: assegno circolare
    :cvar MP04: contanti presso Tesoreria
    :cvar MP05: bonifico
    :cvar MP06: vaglia cambiario
    :cvar MP07: bollettino bancario
    :cvar MP08: carta di pagamento
    :cvar MP09: RID
    :cvar MP10: RID utenze
    :cvar MP11: RID veloce
    :cvar MP12: RIBA
    :cvar MP13: MAV
    :cvar MP14: quietanza erario
    :cvar MP15: giroconto su conti di contabilità speciale
    :cvar MP16: domiciliazione bancaria
    :cvar MP17: domiciliazione postale
    :cvar MP18: bollettino di c/c postale
    :cvar MP19: SEPA Direct Debit
    :cvar MP20: SEPA Direct Debit CORE
    :cvar MP21: SEPA Direct Debit B2B
    :cvar MP22: Trattenuta su somme già riscosse
    :cvar MP23: PagoPA
    """
    MP01 = 'MP01'
    MP02 = 'MP02'
    MP03 = 'MP03'
    MP04 = 'MP04'
    MP05 = 'MP05'
    MP06 = 'MP06'
    MP07 = 'MP07'
    MP08 = 'MP08'
    MP09 = 'MP09'
    MP10 = 'MP10'
    MP11 = 'MP11'
    MP12 = 'MP12'
    MP13 = 'MP13'
    MP14 = 'MP14'
    MP15 = 'MP15'
    MP16 = 'MP16'
    MP17 = 'MP17'
    MP18 = 'MP18'
    MP19 = 'MP19'
    MP20 = 'MP20'
    MP21 = 'MP21'
    MP22 = 'MP22'
    MP23 = 'MP23'
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
    :cvar N6: Inversione contabile (per le operazioni in reverse charge
        ovvero nei casi di autofatturazione per acquisti extra UE di
        servizi ovvero per importazioni di beni nei soli casi previsti)
    :cvar N6_1: Inversione contabile - cessione di rottami e altri
        materiali di recupero
    :cvar N6_2: Inversione contabile - cessione di oro e argento ai
        sensi della legge 7/2000 nonché di oreficeria usata ad OPO
    :cvar N6_3: Inversione contabile - subappalto nel settore edile
    :cvar N6_4: Inversione contabile - cessione di fabbricati
    :cvar N6_5: Inversione contabile - cessione di telefoni cellulari
    :cvar N6_6: Inversione contabile - cessione di prodotti elettronici
    :cvar N6_7: Inversione contabile - prestazioni comparto edile e
        settori connessi
    :cvar N6_8: Inversione contabile - operazioni settore energetico
    :cvar N6_9: Inversione contabile - altri casi
    :cvar N7: IVA assolta in altro stato UE (prestazione di servizi di
        telecomunicazioni, tele-radiodiffusione ed elettronici ex art.
        7-octies lett. a, b, art. 74-sexies DPR 633/72)
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
    N6 = 'N6'
    N6_1 = 'N6.1'
    N6_2 = 'N6.2'
    N6_3 = 'N6.3'
    N6_4 = 'N6.4'
    N6_5 = 'N6.5'
    N6_6 = 'N6.6'
    N6_7 = 'N6.7'
    N6_8 = 'N6.8'
    N6_9 = 'N6.9'
    N7 = 'N7'
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
class RitenutaType(Enum):
    """
    :cvar SI: SI = Cessione / Prestazione soggetta a ritenuta
    """
    SI = 'SI'
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
class TipoCassaType(Enum):
    """
    :cvar TC01: Cassa nazionale previdenza e assistenza avvocati e
        procuratori legali
    :cvar TC02: Cassa previdenza dottori commercialisti
    :cvar TC03: Cassa previdenza e assistenza geometri
    :cvar TC04: Cassa nazionale previdenza e assistenza ingegneri e
        architetti liberi professionisti
    :cvar TC05: Cassa nazionale del notariato
    :cvar TC06: Cassa nazionale previdenza e assistenza ragionieri e
        periti commerciali
    :cvar TC07: Ente nazionale assistenza agenti e rappresentanti di
        commercio (ENASARCO)
    :cvar TC08: Ente nazionale previdenza e assistenza consulenti del
        lavoro (ENPACL)
    :cvar TC09: Ente nazionale previdenza e assistenza medici (ENPAM)
    :cvar TC10: Ente nazionale previdenza e assistenza farmacisti
        (ENPAF)
    :cvar TC11: Ente nazionale previdenza e assistenza veterinari
        (ENPAV)
    :cvar TC12: Ente nazionale previdenza e assistenza impiegati
        dell'agricoltura (ENPAIA)
    :cvar TC13: Fondo previdenza impiegati imprese di spedizione e
        agenzie marittime
    :cvar TC14: Istituto nazionale previdenza giornalisti italiani
        (INPGI)
    :cvar TC15: Opera nazionale assistenza orfani sanitari italiani
        (ONAOSI)
    :cvar TC16: Cassa autonoma assistenza integrativa giornalisti
        italiani (CASAGIT)
    :cvar TC17: Ente previdenza periti industriali e periti industriali
        laureati (EPPI)
    :cvar TC18: Ente previdenza e assistenza pluricategoriale (EPAP)
    :cvar TC19: Ente nazionale previdenza e assistenza biologi (ENPAB)
    :cvar TC20: Ente nazionale previdenza e assistenza professione
        infermieristica (ENPAPI)
    :cvar TC21: Ente nazionale previdenza e assistenza psicologi (ENPAP)
    :cvar TC22: INPS
    """
    TC01 = 'TC01'
    TC02 = 'TC02'
    TC03 = 'TC03'
    TC04 = 'TC04'
    TC05 = 'TC05'
    TC06 = 'TC06'
    TC07 = 'TC07'
    TC08 = 'TC08'
    TC09 = 'TC09'
    TC10 = 'TC10'
    TC11 = 'TC11'
    TC12 = 'TC12'
    TC13 = 'TC13'
    TC14 = 'TC14'
    TC15 = 'TC15'
    TC16 = 'TC16'
    TC17 = 'TC17'
    TC18 = 'TC18'
    TC19 = 'TC19'
    TC20 = 'TC20'
    TC21 = 'TC21'
    TC22 = 'TC22'
class TipoCessionePrestazioneType(Enum):
    """
    :cvar SC: Sconto
    :cvar PR: Premio
    :cvar AB: Abbuono
    :cvar AC: Spesa accessoria
    """
    SC = 'SC'
    PR = 'PR'
    AB = 'AB'
    AC = 'AC'
class TipoDocumentoType(Enum):
    """
    :cvar TD01: Fattura
    :cvar TD02: Acconto / anticipo su fattura
    :cvar TD03: Acconto / anticipo su parcella
    :cvar TD04: Nota di credito
    :cvar TD05: Nota di debito
    :cvar TD06: Parcella
    :cvar TD16: Integrazione fattura reverse charge interno
    :cvar TD17: Integrazione/autofattura per acquisto servizi
        dall'estero
    :cvar TD18: Integrazione per acquisto di beni intracomunitari
    :cvar TD19: Integrazione/autofattura per acquisto di beni ex art.17
        c.2 DPR 633/72
    :cvar TD20: Autofattura per regolarizzazione e integrazione delle
        fatture (ex art. 6 c.9-bis d.lgs. 471/97 o art.46 c.5 D.L.
        331/93)
    :cvar TD21: Autofattura per splafonamento
    :cvar TD22: Estrazione benida Deposito IVA
    :cvar TD23: Estrazione beni da Deposito IVA con versamento dell'IVA
    :cvar TD24: Fattura differita di cui all'art.21, comma 4, terzo
        periodo lett. a) DPR 633/72
    :cvar TD25: Fattura differita di cui all'art.21, comma 4, terzo
        periodo lett. b) DPR 633/72
    :cvar TD26: Cessione di beni ammortizzabili e per passaggi interni
        (ex art.36 DPR 633/72)
    :cvar TD27: Fattura per autoconsumo o per cessioni gratuite senza
        rivalsa
    :cvar TD28: Acquisti da San Marino con IVA (fattura cartacea)
    :cvar TD29: Comunicazione per omessa o irregolare fatturazione da
        parte del cedente/prestatore italiano (art. 6, comma 8, D.Lgs.
        471/97)
    """
    TD01 = 'TD01'
    TD02 = 'TD02'
    TD03 = 'TD03'
    TD04 = 'TD04'
    TD05 = 'TD05'
    TD06 = 'TD06'
    TD16 = 'TD16'
    TD17 = 'TD17'
    TD18 = 'TD18'
    TD19 = 'TD19'
    TD20 = 'TD20'
    TD21 = 'TD21'
    TD22 = 'TD22'
    TD23 = 'TD23'
    TD24 = 'TD24'
    TD25 = 'TD25'
    TD26 = 'TD26'
    TD27 = 'TD27'
    TD28 = 'TD28'
    TD29 = 'TD29'
class TipoRitenutaType(Enum):
    """
    :cvar RT01: Ritenuta di acconto persone fisiche
    :cvar RT02: Ritenuta di acconto persone giuridiche
    :cvar RT03: Contributo INPS
    :cvar RT04: Contributo ENASARCO
    :cvar RT05: Contributo ENPAM
    :cvar RT06: Altro contributo previdenziale
    """
    RT01 = 'RT01'
    RT02 = 'RT02'
    RT03 = 'RT03'
    RT04 = 'RT04'
    RT05 = 'RT05'
    RT06 = 'RT06'
class TipoScontoMaggiorazioneType(Enum):
    """
    :cvar SC: SC = Sconto
    :cvar MG: MG = Maggiorazione
    """
    SC = 'SC'
    MG = 'MG'
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
class DatiAnagraficiCedenteType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
    anagrafica: Optional[AnagraficaType] = field(
        default=None,
        metadata={
            "name": "Anagrafica",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    albo_professionale: Optional[str] = field(
        default=None,
        metadata={
            "name": "AlboProfessionale",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    provincia_albo: Optional[str] = field(
        default=None,
        metadata={
            "name": "ProvinciaAlbo",
            "type": "Element",
            "namespace": "",
            "pattern": r'[A-Z]{2}',
        }
    )
    numero_iscrizione_albo: Optional[str] = field(
        default=None,
        metadata={
            "name": "NumeroIscrizioneAlbo",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,60})',
        }
    )
    data_iscrizione_albo: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataIscrizioneAlbo",
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
class DatiAnagraficiCessionarioType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
    anagrafica: Optional[AnagraficaType] = field(
        default=None,
        metadata={
            "name": "Anagrafica",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
@dataclass
class DatiAnagraficiRappresentanteType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
    anagrafica: Optional[AnagraficaType] = field(
        default=None,
        metadata={
            "name": "Anagrafica",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
@dataclass
class DatiAnagraficiTerzoIntermediarioType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
    anagrafica: Optional[AnagraficaType] = field(
        default=None,
        metadata={
            "name": "Anagrafica",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
@dataclass
class DatiAnagraficiVettoreType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
    anagrafica: Optional[AnagraficaType] = field(
        default=None,
        metadata={
            "name": "Anagrafica",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    numero_licenza_guida: Optional[str] = field(
        default=None,
        metadata={
            "name": "NumeroLicenzaGuida",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
@dataclass
class DatiBolloType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    bollo_virtuale: Optional[BolloVirtualeType] = field(
        default=None,
        metadata={
            "name": "BolloVirtuale",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    importo_bollo: Optional[str] = field(
        default=None,
        metadata={
            "name": "ImportoBollo",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
@dataclass
class DatiCassaPrevidenzialeType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    tipo_cassa: Optional[TipoCassaType] = field(
        default=None,
        metadata={
            "name": "TipoCassa",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    al_cassa: Optional[str] = field(
        default=None,
        metadata={
            "name": "AlCassa",
            "type": "Element",
            "namespace": "",
            "required": True,
            "max_inclusive": "100.00",
            "pattern": r'[0-9]{1,3}\.[0-9]{2}',
        }
    )
    importo_contributo_cassa: Optional[str] = field(
        default=None,
        metadata={
            "name": "ImportoContributoCassa",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    imponibile_cassa: Optional[str] = field(
        default=None,
        metadata={
            "name": "ImponibileCassa",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    aliquota_iva: Optional[str] = field(
        default=None,
        metadata={
            "name": "AliquotaIVA",
            "type": "Element",
            "namespace": "",
            "required": True,
            "max_inclusive": "100.00",
            "pattern": r'[0-9]{1,3}\.[0-9]{2}',
        }
    )
    ritenuta: Optional[RitenutaType] = field(
        default=None,
        metadata={
            "name": "Ritenuta",
            "type": "Element",
            "namespace": "",
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
    riferimento_amministrazione: Optional[str] = field(
        default=None,
        metadata={
            "name": "RiferimentoAmministrazione",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
@dataclass
class DatiRiepilogoType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    aliquota_iva: Optional[str] = field(
        default=None,
        metadata={
            "name": "AliquotaIVA",
            "type": "Element",
            "namespace": "",
            "required": True,
            "max_inclusive": "100.00",
            "pattern": r'[0-9]{1,3}\.[0-9]{2}',
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
    spese_accessorie: Optional[str] = field(
        default=None,
        metadata={
            "name": "SpeseAccessorie",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    arrotondamento: Optional[str] = field(
        default=None,
        metadata={
            "name": "Arrotondamento",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2,8}',
        }
    )
    imponibile_importo: Optional[str] = field(
        default=None,
        metadata={
            "name": "ImponibileImporto",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    imposta: Optional[str] = field(
        default=None,
        metadata={
            "name": "Imposta",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    esigibilita_iva: Optional[EsigibilitaIvatype] = field(
        default=None,
        metadata={
            "name": "EsigibilitaIVA",
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
class DatiRitenutaType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    tipo_ritenuta: Optional[TipoRitenutaType] = field(
        default=None,
        metadata={
            "name": "TipoRitenuta",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    importo_ritenuta: Optional[str] = field(
        default=None,
        metadata={
            "name": "ImportoRitenuta",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    aliquota_ritenuta: Optional[str] = field(
        default=None,
        metadata={
            "name": "AliquotaRitenuta",
            "type": "Element",
            "namespace": "",
            "required": True,
            "max_inclusive": "100.00",
            "pattern": r'[0-9]{1,3}\.[0-9]{2}',
        }
    )
    causale_pagamento: Optional[CausalePagamentoType] = field(
        default=None,
        metadata={
            "name": "CausalePagamento",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
@dataclass
class DatiTrasmissioneType:
    """
    Blocco relativo ai dati di trasmissione della Fattura Elettronica.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
            "pattern": r'[A-Z0-9]{6,7}',
        }
    )
    contatti_trasmittente: Optional[ContattiTrasmittenteType] = field(
        default=None,
        metadata={
            "name": "ContattiTrasmittente",
            "type": "Element",
            "namespace": "",
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
class DettaglioPagamentoType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    beneficiario: Optional[str] = field(
        default=None,
        metadata={
            "name": "Beneficiario",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,200}',
        }
    )
    modalita_pagamento: Optional[ModalitaPagamentoType] = field(
        default=None,
        metadata={
            "name": "ModalitaPagamento",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    data_riferimento_termini_pagamento: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataRiferimentoTerminiPagamento",
            "type": "Element",
            "namespace": "",
        }
    )
    giorni_termini_pagamento: Optional[int] = field(
        default=None,
        metadata={
            "name": "GiorniTerminiPagamento",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 0,
            "max_inclusive": 999,
        }
    )
    data_scadenza_pagamento: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataScadenzaPagamento",
            "type": "Element",
            "namespace": "",
        }
    )
    importo_pagamento: Optional[str] = field(
        default=None,
        metadata={
            "name": "ImportoPagamento",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    cod_ufficio_postale: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodUfficioPostale",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    cognome_quietanzante: Optional[str] = field(
        default=None,
        metadata={
            "name": "CognomeQuietanzante",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    nome_quietanzante: Optional[str] = field(
        default=None,
        metadata={
            "name": "NomeQuietanzante",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,60}',
        }
    )
    cfquietanzante: Optional[str] = field(
        default=None,
        metadata={
            "name": "CFQuietanzante",
            "type": "Element",
            "namespace": "",
            "pattern": r'[A-Z0-9]{16}',
        }
    )
    titolo_quietanzante: Optional[str] = field(
        default=None,
        metadata={
            "name": "TitoloQuietanzante",
            "type": "Element",
            "namespace": "",
            "white_space": "collapse",
            "pattern": r'(\p{IsBasicLatin}{2,10})',
        }
    )
    istituto_finanziario: Optional[str] = field(
        default=None,
        metadata={
            "name": "IstitutoFinanziario",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,80}',
        }
    )
    iban: Optional[str] = field(
        default=None,
        metadata={
            "name": "IBAN",
            "type": "Element",
            "namespace": "",
            "pattern": r'[a-zA-Z]{2}[0-9]{2}[a-zA-Z0-9]{11,30}',
        }
    )
    abi: Optional[str] = field(
        default=None,
        metadata={
            "name": "ABI",
            "type": "Element",
            "namespace": "",
            "pattern": r'[0-9][0-9][0-9][0-9][0-9]',
        }
    )
    cab: Optional[str] = field(
        default=None,
        metadata={
            "name": "CAB",
            "type": "Element",
            "namespace": "",
            "pattern": r'[0-9][0-9][0-9][0-9][0-9]',
        }
    )
    bic: Optional[str] = field(
        default=None,
        metadata={
            "name": "BIC",
            "type": "Element",
            "namespace": "",
            "pattern": r'[A-Z]{6}[A-Z2-9][A-NP-Z0-9]([A-Z0-9]{3}){0,1}',
        }
    )
    sconto_pagamento_anticipato: Optional[str] = field(
        default=None,
        metadata={
            "name": "ScontoPagamentoAnticipato",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    data_limite_pagamento_anticipato: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataLimitePagamentoAnticipato",
            "type": "Element",
            "namespace": "",
        }
    )
    penalita_pagamenti_ritardati: Optional[str] = field(
        default=None,
        metadata={
            "name": "PenalitaPagamentiRitardati",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    data_decorrenza_penale: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataDecorrenzaPenale",
            "type": "Element",
            "namespace": "",
        }
    )
    codice_pagamento: Optional[str] = field(
        default=None,
        metadata={
            "name": "CodicePagamento",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,60})',
        }
    )
@dataclass
class IscrizioneReatype:
    class Meta:
        name = "IscrizioneREAType"
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
class RappresentanteFiscaleCessionarioType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
class ScontoMaggiorazioneType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    tipo: Optional[TipoScontoMaggiorazioneType] = field(
        default=None,
        metadata={
            "name": "Tipo",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    percentuale: Optional[str] = field(
        default=None,
        metadata={
            "name": "Percentuale",
            "type": "Element",
            "namespace": "",
            "max_inclusive": "100.00",
            "pattern": r'[0-9]{1,3}\.[0-9]{2}',
        }
    )
    importo: Optional[str] = field(
        default=None,
        metadata={
            "name": "Importo",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2,8}',
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
class CedentePrestatoreType:
    """
    Blocco relativo ai dati del Cedente / Prestatore.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    dati_anagrafici: Optional[DatiAnagraficiCedenteType] = field(
        default=None,
        metadata={
            "name": "DatiAnagrafici",
            "type": "Element",
            "namespace": "",
            "required": True,
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
    iscrizione_rea: Optional[IscrizioneReatype] = field(
        default=None,
        metadata={
            "name": "IscrizioneREA",
            "type": "Element",
            "namespace": "",
        }
    )
    contatti: Optional[ContattiType] = field(
        default=None,
        metadata={
            "name": "Contatti",
            "type": "Element",
            "namespace": "",
        }
    )
    riferimento_amministrazione: Optional[str] = field(
        default=None,
        metadata={
            "name": "RiferimentoAmministrazione",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
@dataclass
class CessionarioCommittenteType:
    """
    Blocco relativo ai dati del Cessionario / Committente.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    dati_anagrafici: Optional[DatiAnagraficiCessionarioType] = field(
        default=None,
        metadata={
            "name": "DatiAnagrafici",
            "type": "Element",
            "namespace": "",
            "required": True,
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
    rappresentante_fiscale: Optional[RappresentanteFiscaleCessionarioType] = field(
        default=None,
        metadata={
            "name": "RappresentanteFiscale",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class DatiGeneraliDocumentoType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
    dati_ritenuta: list[DatiRitenutaType] = field(
        default_factory=list,
        metadata={
            "name": "DatiRitenuta",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_bollo: Optional[DatiBolloType] = field(
        default=None,
        metadata={
            "name": "DatiBollo",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_cassa_previdenziale: list[DatiCassaPrevidenzialeType] = field(
        default_factory=list,
        metadata={
            "name": "DatiCassaPrevidenziale",
            "type": "Element",
            "namespace": "",
        }
    )
    sconto_maggiorazione: list[ScontoMaggiorazioneType] = field(
        default_factory=list,
        metadata={
            "name": "ScontoMaggiorazione",
            "type": "Element",
            "namespace": "",
        }
    )
    importo_totale_documento: Optional[str] = field(
        default=None,
        metadata={
            "name": "ImportoTotaleDocumento",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    arrotondamento: Optional[str] = field(
        default=None,
        metadata={
            "name": "Arrotondamento",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2}',
        }
    )
    causale: list[str] = field(
        default_factory=list,
        metadata={
            "name": "Causale",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,200}',
        }
    )
    art73: Optional[Art73Type] = field(
        default=None,
        metadata={
            "name": "Art73",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class DatiPagamentoType:
    """
    Blocco relativo ai dati di Pagamento della Fattura Elettronica.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    condizioni_pagamento: Optional[CondizioniPagamentoType] = field(
        default=None,
        metadata={
            "name": "CondizioniPagamento",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    dettaglio_pagamento: list[DettaglioPagamentoType] = field(
        default_factory=list,
        metadata={
            "name": "DettaglioPagamento",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        }
    )
@dataclass
class DatiTrasportoType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    dati_anagrafici_vettore: Optional[DatiAnagraficiVettoreType] = field(
        default=None,
        metadata={
            "name": "DatiAnagraficiVettore",
            "type": "Element",
            "namespace": "",
        }
    )
    mezzo_trasporto: Optional[str] = field(
        default=None,
        metadata={
            "name": "MezzoTrasporto",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,80}',
        }
    )
    causale_trasporto: Optional[str] = field(
        default=None,
        metadata={
            "name": "CausaleTrasporto",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,100}',
        }
    )
    numero_colli: Optional[int] = field(
        default=None,
        metadata={
            "name": "NumeroColli",
            "type": "Element",
            "namespace": "",
            "min_inclusive": 1,
            "max_inclusive": 9999,
        }
    )
    descrizione: Optional[str] = field(
        default=None,
        metadata={
            "name": "Descrizione",
            "type": "Element",
            "namespace": "",
            "pattern": r'[\p{IsBasicLatin}\p{IsLatin-1Supplement}]{1,100}',
        }
    )
    unita_misura_peso: Optional[str] = field(
        default=None,
        metadata={
            "name": "UnitaMisuraPeso",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,10})',
        }
    )
    peso_lordo: Optional[str] = field(
        default=None,
        metadata={
            "name": "PesoLordo",
            "type": "Element",
            "namespace": "",
            "pattern": r'[0-9]{1,4}\.[0-9]{1,2}',
        }
    )
    peso_netto: Optional[str] = field(
        default=None,
        metadata={
            "name": "PesoNetto",
            "type": "Element",
            "namespace": "",
            "pattern": r'[0-9]{1,4}\.[0-9]{1,2}',
        }
    )
    data_ora_ritiro: Optional[XmlDateTime] = field(
        default=None,
        metadata={
            "name": "DataOraRitiro",
            "type": "Element",
            "namespace": "",
        }
    )
    data_inizio_trasporto: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataInizioTrasporto",
            "type": "Element",
            "namespace": "",
        }
    )
    tipo_resa: Optional[str] = field(
        default=None,
        metadata={
            "name": "TipoResa",
            "type": "Element",
            "namespace": "",
            "pattern": r'[A-Z]{3}',
        }
    )
    indirizzo_resa: Optional[IndirizzoType] = field(
        default=None,
        metadata={
            "name": "IndirizzoResa",
            "type": "Element",
            "namespace": "",
        }
    )
    data_ora_consegna: Optional[XmlDateTime] = field(
        default=None,
        metadata={
            "name": "DataOraConsegna",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class DettaglioLineeType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    numero_linea: Optional[int] = field(
        default=None,
        metadata={
            "name": "NumeroLinea",
            "type": "Element",
            "namespace": "",
            "required": True,
            "min_inclusive": 1,
            "max_inclusive": 9999,
        }
    )
    tipo_cessione_prestazione: Optional[TipoCessionePrestazioneType] = field(
        default=None,
        metadata={
            "name": "TipoCessionePrestazione",
            "type": "Element",
            "namespace": "",
        }
    )
    codice_articolo: list[CodiceArticoloType] = field(
        default_factory=list,
        metadata={
            "name": "CodiceArticolo",
            "type": "Element",
            "namespace": "",
        }
    )
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
    quantita: Optional[str] = field(
        default=None,
        metadata={
            "name": "Quantita",
            "type": "Element",
            "namespace": "",
            "pattern": r'[0-9]{1,12}\.[0-9]{2,8}',
        }
    )
    unita_misura: Optional[str] = field(
        default=None,
        metadata={
            "name": "UnitaMisura",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,10})',
        }
    )
    data_inizio_periodo: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataInizioPeriodo",
            "type": "Element",
            "namespace": "",
        }
    )
    data_fine_periodo: Optional[XmlDate] = field(
        default=None,
        metadata={
            "name": "DataFinePeriodo",
            "type": "Element",
            "namespace": "",
        }
    )
    prezzo_unitario: Optional[str] = field(
        default=None,
        metadata={
            "name": "PrezzoUnitario",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2,8}',
        }
    )
    sconto_maggiorazione: list[ScontoMaggiorazioneType] = field(
        default_factory=list,
        metadata={
            "name": "ScontoMaggiorazione",
            "type": "Element",
            "namespace": "",
        }
    )
    prezzo_totale: Optional[str] = field(
        default=None,
        metadata={
            "name": "PrezzoTotale",
            "type": "Element",
            "namespace": "",
            "required": True,
            "pattern": r'[\-]?[0-9]{1,11}\.[0-9]{2,8}',
        }
    )
    aliquota_iva: Optional[str] = field(
        default=None,
        metadata={
            "name": "AliquotaIVA",
            "type": "Element",
            "namespace": "",
            "required": True,
            "max_inclusive": "100.00",
            "pattern": r'[0-9]{1,3}\.[0-9]{2}',
        }
    )
    ritenuta: Optional[RitenutaType] = field(
        default=None,
        metadata={
            "name": "Ritenuta",
            "type": "Element",
            "namespace": "",
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
    riferimento_amministrazione: Optional[str] = field(
        default=None,
        metadata={
            "name": "RiferimentoAmministrazione",
            "type": "Element",
            "namespace": "",
            "pattern": r'(\p{IsBasicLatin}{1,20})',
        }
    )
    altri_dati_gestionali: list[AltriDatiGestionaliType] = field(
        default_factory=list,
        metadata={
            "name": "AltriDatiGestionali",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class RappresentanteFiscaleType:
    """
    Blocco relativo ai dati del Rappresentante Fiscale.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    dati_anagrafici: Optional[DatiAnagraficiRappresentanteType] = field(
        default=None,
        metadata={
            "name": "DatiAnagrafici",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
@dataclass
class TerzoIntermediarioSoggettoEmittenteType:
    """
    Blocco relativo ai dati del Terzo Intermediario che emette fattura elettronica
    per conto del Cedente/Prestatore.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    dati_anagrafici: Optional[DatiAnagraficiTerzoIntermediarioType] = field(
        default=None,
        metadata={
            "name": "DatiAnagrafici",
            "type": "Element",
            "namespace": "",
            "required": True,
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
class DatiBeniServiziType:
    """
    Blocco relativo ai dati di Beni Servizi della Fattura   Elettronica.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    dettaglio_linee: list[DettaglioLineeType] = field(
        default_factory=list,
        metadata={
            "name": "DettaglioLinee",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        }
    )
    dati_riepilogo: list[DatiRiepilogoType] = field(
        default_factory=list,
        metadata={
            "name": "DatiRiepilogo",
            "type": "Element",
            "namespace": "",
            "min_occurs": 1,
        }
    )
@dataclass
class DatiGeneraliType:
    """
    Blocco relativo ai Dati Generali della Fattura Elettronica.
    """
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    dati_generali_documento: Optional[DatiGeneraliDocumentoType] = field(
        default=None,
        metadata={
            "name": "DatiGeneraliDocumento",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    dati_ordine_acquisto: list[DatiDocumentiCorrelatiType] = field(
        default_factory=list,
        metadata={
            "name": "DatiOrdineAcquisto",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_contratto: list[DatiDocumentiCorrelatiType] = field(
        default_factory=list,
        metadata={
            "name": "DatiContratto",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_convenzione: list[DatiDocumentiCorrelatiType] = field(
        default_factory=list,
        metadata={
            "name": "DatiConvenzione",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_ricezione: list[DatiDocumentiCorrelatiType] = field(
        default_factory=list,
        metadata={
            "name": "DatiRicezione",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_fatture_collegate: list[DatiDocumentiCorrelatiType] = field(
        default_factory=list,
        metadata={
            "name": "DatiFattureCollegate",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_sal: list[DatiSaltype] = field(
        default_factory=list,
        metadata={
            "name": "DatiSAL",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_ddt: list[DatiDdttype] = field(
        default_factory=list,
        metadata={
            "name": "DatiDDT",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_trasporto: Optional[DatiTrasportoType] = field(
        default=None,
        metadata={
            "name": "DatiTrasporto",
            "type": "Element",
            "namespace": "",
        }
    )
    fattura_principale: Optional[FatturaPrincipaleType] = field(
        default=None,
        metadata={
            "name": "FatturaPrincipale",
            "type": "Element",
            "namespace": "",
        }
    )
@dataclass
class FatturaElettronicaHeaderType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
    rappresentante_fiscale: Optional[RappresentanteFiscaleType] = field(
        default=None,
        metadata={
            "name": "RappresentanteFiscale",
            "type": "Element",
            "namespace": "",
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
    terzo_intermediario_osoggetto_emittente: Optional[TerzoIntermediarioSoggettoEmittenteType] = field(
        default=None,
        metadata={
            "name": "TerzoIntermediarioOSoggettoEmittente",
            "type": "Element",
            "namespace": "",
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
class FatturaElettronicaBodyType:
    class Meta:
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

    dati_generali: Optional[DatiGeneraliType] = field(
        default=None,
        metadata={
            "name": "DatiGenerali",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    dati_beni_servizi: Optional[DatiBeniServiziType] = field(
        default=None,
        metadata={
            "name": "DatiBeniServizi",
            "type": "Element",
            "namespace": "",
            "required": True,
        }
    )
    dati_veicoli: Optional[DatiVeicoliType] = field(
        default=None,
        metadata={
            "name": "DatiVeicoli",
            "type": "Element",
            "namespace": "",
        }
    )
    dati_pagamento: list[DatiPagamentoType] = field(
        default_factory=list,
        metadata={
            "name": "DatiPagamento",
            "type": "Element",
            "namespace": "",
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
        target_namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"

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
class FatturaElettronica(FatturaElettronicaType):
    """
    XML schema fatture destinate a PA e privati in forma ordinaria 1.2.3.
    """
    class Meta:
        namespace = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"