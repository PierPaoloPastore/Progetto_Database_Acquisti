# Project Overview

## Obiettivo

Questo progetto è una webapp Flask/Python per gestire l’intero ciclo di vita dei **documenti di acquisto** dell’azienda e del relativo ciclo passivo.

Oggi è centrato sulle **fatture di acquisto FatturaPA** (import XML → revisione → gestione copia fisica → pianificazione e registrazione pagamenti), con funzioni di:

- ricerca e filtri avanzati sulle fatture,
- gestione fornitori e intestatari (legal entities),
- categorizzazione analitica delle righe,
- note operative,
- gestione scadenze e pagamenti,
- gestione DDT/bolle collegate alle fatture,
- reportistica ed export CSV.

Nel medio periodo l’obiettivo è estendere il dominio ad altri **documenti economici e fiscali**, inclusi:

- assicurazioni,
- F24,
- scontrini,
- CBILL,
- MAV,
- contratti di affitto (con rate mensili),
- tributi/tasse,

mantenendo un unico flusso di lavoro coerente per revisione, scadenziario, pagamenti e controllo documentale.

---

## Funzioni principali (oggi)

### Import e modellazione dei documenti

- Import **XML FatturaPA** da cartella configurabile.
- Parsing FatturaPA → entità dominio (`Document` con `document_type='invoice'`, `Supplier`, `LegalEntity`, `InvoiceLine`, `VatSummary`).
- Salvataggio coerente dei dati di testata, righe e riepilogo IVA.
- **Architettura estendibile**: il sistema usa un **supertipo unificato** (`documents`) per gestire:
  - Fatture FatturaPA (immediate e differite)
  - F24
  - Assicurazioni
  - MAV / CBILL
  - Scontrini
  - Affitti (rate mensili)
  - Tributi / Tasse
  - Altri documenti economici

### Revisione e controllo documentale

- Revisione dei nuovi documenti importati con stato (`doc_status`: imported, verified, rejected, cancelled, archived).
- Gestione delle **copie fisiche**:
  - richiesta, ricezione, upload/scansione su file system
  - tracciamento dello stato (`physical_copy_status`)
- Gestione delle **bolle / DDT** tramite la tabella `delivery_notes`:
  - DDT attesi da XML (`source = xml_expected`)
  - DDT reali importati come PDF (`source = pdf_import`)
  - stato di matching (`unmatched`, `matched`, `missing`)
  - collegamento alle fatture differite

### Scadenze e pagamenti

- Modellazione delle scadenze in tabella `payments`:
  - **Una o più scadenze per documento** (qualsiasi tipo)
  - FK unificato: `payment.document_id` → `documents.id`
  - Importi attesi, importi pagati, stato (`unpaid`, `planned`, `pending`, `partial`, `paid`, `overdue`)
- Import e gestione dei **documenti di pagamento bancari** (`payment_documents`):
  - PDF di bonifici, MAV, assegni, F24, ecc.
  - **Novità:** `supplier_id` per riconciliazione diretta
  - Collegamento M:N a più scadenze tramite `payment_document_links`
- **Scadenziario unificato** per tutti i tipi di documento

### Anagrafiche e classificazione

- Gestione **fornitori** (`suppliers`) con P.IVA unique e `fiscal_code` (rinominato da tax_code).

Gestione intestatari (legal_entities) con P.IVA unique e pulizia colonna tax_code (rimossa).
Gestione categorie (categories) e loro assegnazione alle righe fattura (invoice_lines).
Gestione note interne (notes) collegate ai documenti (qualsiasi tipo).

Export e analisi

Export CSV per analisi contabile esterna.
Funzioni di supporto a estratti conto fornitori (cross-document), riepiloghi IVA, sintesi per legal entity.
Report aggregati per tipo documento (fatture, F24, assicurazioni, ecc.).

### Import e modellazione delle fatture

- Import XML FatturaPA da cartella configurabile.
- Parsing FatturaPA → entità dominio (Invoice, Supplier, LegalEntity, InvoiceLine, VatSummary).
- Salvataggio coerente dei dati di testata, righe e riepilogo IVA.
- Gestione del tipo fattura:
  - **immediata** (senza DDT),
  - **differita** (con riferimenti a uno o più DDT).

### Revisione e controllo documentale

- Revisione delle nuove fatture importate con stato documento (imported, confirmed, cancelled, …).
- Gestione delle **copie fisiche**:
  - richiesta,
  - ricezione,
  - upload/scansione su file system,
  - tracciamento dello stato (`physical_copy_status`).
- Gestione delle **bolle / DDT** tramite la tabella `delivery_notes`:
  - DDT attesi da XML (`source = xml_expected`),
  - DDT reali importati come PDF (`source = pdf_import`),
  - stato di matching (`unmatched`, `matched`, `missing`, …),
  - collegamento alle fatture differite.

### Scadenze e pagamenti

- Modellazione delle scadenze in tabella `payments`:
  - una o più scadenze per fattura,
  - importi attesi, importi pagati, stato (`planned`, `pending`, `partial`, `paid`, …).
- Import e gestione dei **documenti di pagamento bancari** (`payment_documents`):
  - PDF di bonifici, MAV, assegni, ecc.,
  - importo e data del movimento,
  - possibile collegamento a più scadenze tramite tabella ponte `payment_document_links`.
- Scadenziario basato sulle righe `payments` con stato aperto, non solo sulle fatture.

### Anagrafiche e classificazione

- Gestione **fornitori** (`suppliers`) e **intestatari** (`legal_entities`).
- Gestione **categorie** (`categories`) e loro assegnazione alle righe fattura (`invoice_lines`).
- Gestione **note interne** (`notes`) collegate alle fatture.

### Export e analisi

- Export CSV per analisi contabile esterna.
- Funzioni di supporto a estratti conto fornitori, riepiloghi IVA, sintesi per legal entity.

---

## Direzioni di sviluppo

- Generalizzazione del modello da “fattura” a **documento/movimento di acquisto**, mantenendo `invoices` come primo caso concreto.
- Integrazione di documenti PDF per:
  - assicurazioni,
  - F24,
  - MAV/CBILL,
  - affitti,
  - altri tributi/tasse,
  con flussi semi-guidati analoghi a DDT e pagamenti.
- Migliorare l’automazione nella **riconciliazione**:
  - fatture ↔ DDT (attesi vs reali),
  - fatture/scadenze ↔ documenti di pagamento bancari.
- Migliorare UX delle schermate di:
  - revisione fatture,
  - gestione scadenziario,
  - gestione DDT mancanti (incluse azioni rapide, es. email precompilate per richiesta copie).
