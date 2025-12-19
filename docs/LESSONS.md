# Lessons Learned

## Backend / SQLAlchemy patterns
- Internal Mapping: disaccoppiare gli argomenti delle funzioni pubbliche dai campi del DB quando i nomi divergono (es. `payment_date` -> `due_date`). Mappare esplicitamente nel body della funzione.
- Runtime Safety: Verificare l'esistenza degli attributi del Modello prima di usarli in `order_by` o filtri.
- **Enum Case Sensitivity**: Database enum values must match exactly in code comparisons. Use lowercase for status values ('paid', 'partial', 'unpaid') not uppercase ('PAID', 'PARTIAL') to avoid comparison failures.
- **ID Type Mismatch**: UI forms may send entity IDs that differ from what backend expects. If UI iterates over Documents but backend expects Payment IDs, add mapping logic in service layer or change UI to match backend expectations.

## Flask / Templating
- **Name Mismatch Risk**: Se il codice Python punta a `view_A.html` e tu crei `view_B.html`, la UI non cambierà. Allineare sempre Route e Filename.
- **Cleanup**: Rimuovere i vecchi template durante il refactoring per evitare 'Stale UI' (vecchia interfaccia caricata silenziosamente).
- **srcdoc vs src**: iframe elements with `srcdoc` attribute will prioritize srcdoc over dynamically set `src` attribute. Remove srcdoc and use placeholder div instead for dynamic content loading.

## FatturaPA / Parsing & P7M
- **Fonte unica**: seguire sempre `docs/fatturapa/PARSING_REFERENCE.md` per obbligatorietà, fallback e classificazione (imported/skip/error). Non reinterpretare i PDF.
- **P7M in binario**: aprire `.p7m` sempre in `rb`. Considerare base64 solo se tutti i byte sono nel set base64; altrimenti trattare come DER. Niente decodifica UTF-8 testuale.
- **Ricerca XML**: trovare `<?xml`/`<FatturaElettronica` nei bytes decodificati/DER e tagliare fino alla chiusura. Pulizia minima: rimuovere solo NUL e control < 0x20 eccetto `\t\n\r`.
- **Encoding sporchi**: se lxml segnala “not proper UTF-8” ma il prolog è UTF-8, provare decode `cp1252` → UTF-8 (fallback `latin-1`), poi riparsare. Loggare warning con encoding usato; se fallisce salvare il blob in `import_debug/xml_encoding_failed/`.
- **Non mascherare errori**: non usare `recover=True` se non come ultimissima spiaggia loggata. Conservare head_bytes/size nei messaggi di errore e dumpare XML problematici in `import_debug/p7m_failed/` per diagnosi.
- **Skip consapevole**: classificare metadati/notifiche SDI per lo skip, ma non confondere XML illeggibile con metadati. ParseError (non parsabile) ≠ Skip (non fattura).

## Revisione documenti (UI/Service)
- **Endpoint e metodi devono esistere nella classe**: se un route chiama `DocumentService.delete_document`, assicurarsi che il metodo sia davvero definito come `@staticmethod` nella classe e, se esposto a livello modulo, che il wrapper punti lì. Evita definizioni annidate o fuori scope che rompono l’import al restart.
- **Conferma deve cambiare stato**: nel flusso di review, non lasciare `doc_status` a `imported` quando l’utente conferma; se il select è vuoto o “imported”, forzare a `verified` così il documento esce dalla coda di revisione.
- **Banner di revisione**: nel dettaglio documento, per stato `imported` mostra un solo pulsante “Vai alla revisione” invece di azioni di conferma/scarta duplicate; l’azione vera va eseguita nella pagina di review.
