# Gestione Import P7M - Troubleshooting

## ✅ Soluzioni implementate

### 1. Estrazione XML da P7M
- ✅ Decodifica Base64 automatica
- ✅ Pulizia caratteri corrotti
- ✅ Gestione encoding windows-1252 e UTF-8
- ✅ Fallback per XML malformati (parser con `recover=True`)

### 2. Validazione robusta
- ✅ Fallback per supplier name vuoto
- ✅ Gestione legal_entity da P7M
- ✅ Error handling per parsing failures

---

## 🔍 Errori comuni e soluzioni

### ❌ Errore: "legal_entity_id è obbligatorio"

**Causa:** Il sistema non riesce a estrarre `CessionarioCommittente` dal P7M.

**Soluzione:**
1. Verifica che il P7M contenga il nodo `<CessionarioCommittente>`
2. Se manca, specifica `legal_entity_id` manualmente nell'import:
   ```python
   run_import(folder="...", legal_entity_id=1)
   ```

**Fix applicato:**
- `_extract_header_data()` ora gestisce correttamente i P7M
- Pulizia caratteri corrotti prima del parsing

---

### ❌ Errore: "Column 'name' cannot be null"

**Causa:** Il fornitore non ha denominazione nell'XML.

**Soluzione automatica applicata:**
```python
# Fallback nel parser:
if not name:
    if vat_number:
        name = f"P.IVA {vat_number}"
    elif fiscal_code:
        name = f"CF {fiscal_code}"
    else:
        name = "Fornitore sconosciuto"
```

**Azione manuale:**
Dopo l'import, aggiorna il nome del fornitore nel database:
```sql
UPDATE suppliers 
SET name = 'Nome Corretto' 
WHERE vat_number = 'XXX';
```

---

### ❌ Errore: "Opening and ending tag mismatch"

**Causa:** XML malformato con typo nei tag (es. `</DatiRieupilogo>` invece di `</DatiRiepilogo>`).

**Soluzione automatica applicata:**
- Parser lxml con `recover=True` che corregge automaticamente errori XML minori
- Il file viene importato comunque, con warning nel log

**Se persiste:**
1. Controlla il file XML originale
2. Correggi manualmente il typo
3. Ri-importa

---

### ❌ Errore: "'tuple' object has no attribute 'id'"

**Causa:** Bug nella funzione `_get_or_create_legal_entity()`.

**Fix da applicare:**
Verifica che la funzione restituisca un oggetto `LegalEntity`, non una tupla:

```python
def _get_or_create_legal_entity(header_data: Dict) -> LegalEntity:
    # ...
    return legal_entity  # ← deve essere oggetto, non (legal_entity, created)
```

---

## 📂 File corrotti o non parsabili

Alcuni file P7M potrebbero essere troppo corrotti per essere recuperati.

**Workflow:**
1. Il sistema registra l'errore in `import_logs`
2. Il file viene saltato
3. Puoi:
   - Richiedere una nuova copia del file al fornitore
   - Estrarre manualmente l'XML dal P7M con tool esterni
   - Importare l'XML estratto come file `.xml` normale

**Tool esterni per estrarre P7M:**
```bash
# Con OpenSSL
openssl smime -verify -in file.p7m -inform DER -noverify -out file.xml

# Con dike (tool italiano)
# GUI disponibile su https://www.firmacerta.it
```

---

## 🛠 Manutenzione

### Pulizia file già importati

Se hai file duplicati o errori ripetuti:

```sql
-- Trova file importati multipli
SELECT file_name, COUNT(*) as count
FROM import_logs
GROUP BY file_name
HAVING COUNT(*) > 1;

-- Elimina log di errore vecchi
DELETE FROM import_logs
WHERE status = 'error' 
  AND created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

### Monitoring

Verifica gli errori recenti:
```sql
SELECT file_name, status, message, created_at
FROM import_logs
WHERE status = 'error'
ORDER BY created_at DESC
LIMIT 20;
```

---

## 📊 Statistiche import

```sql
-- Statistiche per tipo di file
SELECT 
    CASE 
        WHEN file_name LIKE '%.p7m' THEN 'P7M'
        WHEN file_name LIKE '%.P7M' THEN 'P7M'
        ELSE 'XML'
    END as tipo_file,
    status,
    COUNT(*) as totale
FROM import_logs
GROUP BY tipo_file, status
ORDER BY tipo_file, status;
```

---

## ✅ Checklist pre-deployment

- [ ] Sostituisci `app/parsers/fatturapa_parser.py`
- [ ] Sostituisci `app/services/import_service.py`
- [ ] Verifica che non ci siano conflitti con codice custom
- [ ] Testa su un subset di file P7M problematici
- [ ] Monitora i log dopo il deploy

---

## 🆘 Support

Se riscontri errori non coperti:
1. Controlla `logs/app.log` per il traceback completo
2. Verifica il file XML estratto (salvato in temp)
3. Controlla che il P7M sia valido con tool esterni
4. Raccogli:
   - Nome file problematico
   - Messaggio errore completo
   - Dimensione file
   - Fornitore emittente