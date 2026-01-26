# PARSING_REFERENCE.md
## FatturaPA — Parsing Reference Operativa (Ordinaria v1.4)

## Asset ufficiali
Gli XSD/XSL ufficiali FatturaPA sono versionati in `resources/fatturapa/`.


### Scopo
Questo documento definisce la **specifica operativa interna** per il parsing delle FatturePA (XML),
derivata dalle Specifiche Tecniche ufficiali.
È la **fonte di verità** per:
- parsing XML
- mapping verso DTO
- gestione fallback
- classificazione errori / warning / skip

Non sostituisce la normativa, ma ne codifica le regole **utili all’implementazione**.

---

## 0. Regole generali

- I tag dei campi **non valorizzati NON devono comparire** nell’XML.
- Il namespace XML **non deve influenzare** il parsing (usare local-name).
- Ogni `FatturaElettronicaBody` rappresenta **un documento applicativo distinto**.
- L’assenza di un campo obbligatorio genera **non conformità**, ma non sempre blocca il parsing contabile.
- Prima del parsing: estrazione P7M (base64/DER), pulizia control char, rimozione byte non ASCII nei nomi tag, fallback encoding (cp1252/latin-1). `recover=True` solo come ultima spiaggia.
- Parser: xsdata come percorso principale; fallback al parser legacy lxml se xsdata fallisce o restituisce 0 body.

---

## 1. Struttura generale

- Root: `FatturaElettronica`
- Blocchi principali:
  - `FatturaElettronicaHeader` (1..1)
  - `FatturaElettronicaBody` (1..N)

**Policy applicativa**
- 1 Header condiviso
- N Body → N documenti applicativi

---

## 2. Header

### 2.1 DatiTrasmissione (OBBLIGATORIO)

Percorso:
```

/FatturaElettronica/FatturaElettronicaHeader/DatiTrasmissione

```

#### Campi

- **IdTrasmittente** (OBBLIGATORIO)
  - IdPaese (OBBLIGATORIO)
  - IdCodice (OBBLIGATORIO)
  - Fallback: nessuno  
  - Assenza → non conforme (warning forte)

- **ProgressivoInvio** (OBBLIGATORIO)
  - Assenza → non conforme

- **FormatoTrasmissione** (OBBLIGATORIO)
  - Valori tipici: `FPA12`, `FPR12`
  - Assenza → non conforme

- **CodiceDestinatario** (OBBLIGATORIO)
  - Valori speciali:
    - `0000000` → canale PEC / canale non noto
    - `XXXXXXX` → soggetto non residente
  - Se presente ma invalido → warning, parsing contabile consentito

- **PECDestinatario** (FACOLTATIVO)
  - Ammesso solo se `CodiceDestinatario == "0000000"`
  - Se presente in altri casi → ignorare + warning

- **ContattiTrasmittente** (FACOLTATIVO)
  - Telefono
  - Email

---

## 3. CedentePrestatore

### 3.1 DatiAnagrafici (OBBLIGATORIO)

Percorso:
```

.../CedentePrestatore/DatiAnagrafici

```

#### Identificazione fiscale

- **IdFiscaleIVA** (OBBLIGATORIO nel modello ordinario)
  - IdPaese
  - IdCodice
  - Fallback operativo:
    - Se assente ma presente CodiceFiscale → usare CF come identificativo debole
    - Documento marcato come *non conforme*

- **CodiceFiscale** (FACOLTATIVO)
  - Può coesistere con IdFiscaleIVA

#### Anagrafica (OBBLIGATORIA come blocco)

- **Denominazione**
- **Nome**
- **Cognome**

**Regola**
- Deve essere presente:
  - Denominazione  
  **oppure**
  - Nome + Cognome

**Fallback nome soggetto**
1. Denominazione
2. Nome + Cognome
3. null + warning (dato anagrafico incompleto)

- **RegimeFiscale** (OBBLIGATORIO)
  - Assenza → non conforme

---

### 3.2 Sede (OBBLIGATORIO come blocco)

Percorso:
```

.../CedentePrestatore/Sede

```

#### Campi

- Indirizzo (OBBLIGATORIO)
- NumeroCivico (FACOLTATIVO)
- CAP (OBBLIGATORIO)
- Comune (OBBLIGATORIO)
- Provincia (FACOLTATIVO, ma attesa se Nazione = IT)
- Nazione (OBBLIGATORIO)

**Fallback indirizzo stampabile**
```

Indirizzo + (" " + NumeroCivico se presente)

```

---

## 4. CessionarioCommittente

### 4.1 DatiAnagrafici (OBBLIGATORIO)

- **IdFiscaleIVA** (FACOLTATIVO)
- **CodiceFiscale** (FACOLTATIVO)

**Regole**
- Possono coesistere
- Se uno solo presente → usarlo come identificativo principale

#### Anagrafica
Stesse regole del Cedente:
- Denominazione  
- oppure Nome + Cognome  
- fallback identico

---

### 4.2 Sede
Stesse regole e fallback della sede Cedente.

---

### 4.3 Identificazione intestatario (match applicativo)

Queste regole governano la risoluzione della `LegalEntity` in import:

- **Chiave primaria**: usare sempre il **Codice Fiscale** se presente.
- **Fallback**: usare la **P.IVA** solo se il Codice Fiscale e' assente.
- **Normalizzazione**: rimuovere spazi e caratteri non alfanumerici, convertire in maiuscolo prima di confrontare.
- **Batch import**: l'intestatario e' calcolato **per file**; non va riutilizzato tra file diversi (solo tra body dello stesso file).
- **Riparazione dati**: se un'entita' trovata per P.IVA non ha CF (o ha CF uguale alla P.IVA), aggiornarla con il CF estratto.

Per debug in caso di mismatch, loggare per ogni file i campi estratti:
`cc_name`, `vat_number`, `fiscal_code` e le versioni normalizzate (`*_clean`).

---

## 5. Documento (Body)

Percorso:
```

/FatturaElettronica/FatturaElettronicaBody

```

Ogni Body → **1 documento applicativo**

---

### 5.1 DatiGeneraliDocumento (OBBLIGATORIO)

- **TipoDocumento** (OBBLIGATORIO)
- **Divisa** (OBBLIGATORIO)
- **Data** (OBBLIGATORIO)
- **Numero** (OBBLIGATORIO)

- **ImportoTotaleDocumento** (FACOLTATIVO)
  - Fallback: calcolo dai Totali

- **Arrotondamento** (FACOLTATIVO)
  - Fallback: 0

- **Causale** (FACOLTATIVO, 0..N)
  - Fallback: concatena con `\n`

- **Art73** (FACOLTATIVO)
  - Fallback: null / false

---

## 6. Linee documento

Percorso:
```

.../DatiBeniServizi/DettaglioLinee

```

Per ogni linea:

- NumeroLinea (OBBLIGATORIO)
- Descrizione (OBBLIGATORIO)
- Quantita (FACOLTATIVO)
  - Fallback: null (oppure 1 solo se richiesto da logica applicativa)
- PrezzoUnitario (OBBLIGATORIO)
- PrezzoTotale (OBBLIGATORIO)
- AliquotaIVA (OBBLIGATORIO)
  - Se non applicabile → 0.00
- Natura (CONDIZIONATA)
  - Obbligatoria se AliquotaIVA = 0.00
  - Fallback: null + warning
- Ritenuta (FACOLTATIVO)
  - Fallback: false

---

## 7. Totali

### 7.1 DatiRiepilogo (OBBLIGATORIO, 1..N)

Percorso:
```

.../DatiBeniServizi/DatiRiepilogo

```

Per ogni blocco:

- AliquotaIVA (OBBLIGATORIO)
- Natura (CONDIZIONATA)
- ImponibileImporto (OBBLIGATORIO)
- Imposta (OBBLIGATORIO)
- EsigibilitaIVA (FACOLTATIVO)
- RiferimentoNormativo (CONDIZIONATO)
- SpeseAccessorie (FACOLTATIVO)
- Arrotondamento (FACOLTATIVO)

---

### 7.2 Fallback ImportoTotaleDocumento

Se `ImportoTotaleDocumento` è assente:

1. `sum_imponibile = Σ(ImponibileImporto)`
2. `sum_imposta = Σ(Imposta)`
3. `totale = sum_imponibile + sum_imposta`
4. Applica Arrotondamento se presente

**Fallback di emergenza (non conforme)**
- Se `DatiRiepilogo` manca:
  - ricostruire dai DettaglioLinee
  - marcare il documento come *importato con warning di non conformità*
  - sottoporre a revisione manuale

---

## 8. Classificazione esito import

- **Imported**
  - Conforme
  - Conforme con warning

- **Skipped**
  - Metadati
  - Notifiche SDI
  - File non fattura

- **Error**
  - XML non parsabile
  - Mapping impossibile

---

## 9. Uso di questo documento

Questo file:
- ha priorità sulle interpretazioni automatiche
- deve essere citato esplicitamente nei prompt a Codex
- governa parsing, fallback e test manuali

Ogni modifica futura **va versionata** e motivata.
