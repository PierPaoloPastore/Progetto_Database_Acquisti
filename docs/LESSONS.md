# Lessons Learned

## Backend / SQLAlchemy patterns
- Internal Mapping: disaccoppiare gli argomenti delle funzioni pubbliche dai campi del DB quando i nomi divergono (es. `payment_date` -> `due_date`). Mappare esplicitamente nel body della funzione.
- Runtime Safety: Verificare l'esistenza degli attributi del Modello prima di usarli in `order_by` o filtri.
