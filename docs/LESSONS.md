# Lessons Learned

## Backend / SQLAlchemy patterns
- Internal Mapping: disaccoppiare gli argomenti delle funzioni pubbliche dai campi del DB quando i nomi divergono (es. `payment_date` -> `due_date`). Mappare esplicitamente nel body della funzione.
- Runtime Safety: Verificare l'esistenza degli attributi del Modello prima di usarli in `order_by` o filtri.

## Flask / Templating
- **Name Mismatch Risk**: Se il codice Python punta a `view_A.html` e tu crei `view_B.html`, la UI non cambierà. Allineare sempre Route e Filename.
- **Cleanup**: Rimuovere i vecchi template durante il refactoring per evitare 'Stale UI' (vecchia interfaccia caricata silenziosamente).
