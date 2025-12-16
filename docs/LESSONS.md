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
