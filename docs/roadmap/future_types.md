Last updated: 2025-12-15

# Future Document Types – Implementation Guide

Questo file descrive come estendere il sistema per gestire nuovi tipi di documento oltre a quelli già supportati.

---

## Tipi Documento Già Supportati

Il sistema attualmente supporta **nativamente** questi tipi tramite la tabella `documents`:

✅ **Fatture FatturaPA** (`document_type = 'invoice'`)  
✅ **F24** (`document_type = 'f24'`)  
✅ **Assicurazioni** (`document_type = 'insurance'`)  
✅ **MAV** (`document_type = 'mav'`)  
✅ **CBILL** (`document_type = 'cbill'`)  
✅ **Scontrini** (`document_type = 'receipt'`)  
✅ **Affitti** (`document_type = 'rent'`)  
✅ **Tributi/Tasse** (`document_type = 'tax'`)  
✅ **Altro** (`document_type = 'other'`)

---

## Come Aggiungere un Nuovo Tipo Documento

### Esempio: Contratti di Manutenzione

#### Step 1: Aggiorna CHECK Constraint
```sql
ALTER TABLE documents DROP CONSTRAINT chk_documents_type;
ALTER TABLE documents ADD CONSTRAINT chk_documents_type
  CHECK (document_type IN (
    'invoice', 'f24', 'insurance', 'mav', 'cbill', 
    'receipt', 'rent', 'tax',
    'maintenance_contract',  -- NUOVO
    'other'
  ));
```

#### Step 2: Aggiungi Colonne Specifiche (opzionale)
```sql
ALTER TABLE documents 
  ADD COLUMN maintenance_contract_number VARCHAR(64) DEFAULT NULL COMMENT 'Numero contratto manutenzione',
  ADD COLUMN maintenance_start_date DATE DEFAULT NULL,
  ADD COLUMN maintenance_end_date DATE DEFAULT NULL,
  ADD COLUMN maintenance_frequency VARCHAR(32) DEFAULT NULL COMMENT 'monthly, quarterly, annual';
```

#### Step 3: Aggiungi CHECK Constraint Condizionale
```sql
ALTER TABLE documents ADD CONSTRAINT chk_documents_maintenance
  CHECK (
    (document_type = 'maintenance_contract' AND maintenance_contract_number IS NOT NULL)
    OR (document_type != 'maintenance_contract' AND maintenance_contract_number IS NULL)
  );
```

#### Step 4: Aggiorna Modello Python
```python
# app/models/document.py

class Document(db.Model):
    # ... colonne esistenti ...
    
    # Colonne specifiche manutenzione
    maintenance_contract_number = db.Column(db.String(64))
    maintenance_start_date = db.Column(db.Date)
    maintenance_end_date = db.Column(db.Date)
    maintenance_frequency = db.Column(db.String(32))
    
    @property
    def is_maintenance_contract(self):
        return self.document_type == 'maintenance_contract'
```

#### Step 5: (Opzionale) Aggiungi Tabella Specializzata

Se il nuovo tipo ha molti dettagli specifici, crea una tabella dedicata:
```sql
CREATE TABLE maintenance_contract_details (
  id INT PRIMARY KEY AUTO_INCREMENT,
  document_id INT NOT NULL,
  service_description TEXT,
  equipment_list TEXT,
  technician_name VARCHAR(128),
  ...
  FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);
```

#### Step 6: Implementa Import/Creazione
```python
# app/services/document_service.py

def create_maintenance_contract(data):
    document = Document(
        document_type='maintenance_contract',
        supplier_id=data['supplier_id'],
        legal_entity_id=data['legal_entity_id'],
        document_number=data['contract_number'],
        document_date=data['start_date'],
        total_gross_amount=data['annual_amount'],
        maintenance_contract_number=data['contract_number'],
        maintenance_start_date=data['start_date'],
        maintenance_end_date=data['end_date'],
        maintenance_frequency=data['frequency'],
        doc_status='imported'
    )
    db.session.add(document)
    
    # Crea scadenze automatiche (es. rate mensili)
    create_recurring_payments(document, data['frequency'])
    
    db.session.commit()
    return document
```

---

## Vantaggi Architettura Attuale

### ✅ Nessun Refactor Necessario

- `payments` funziona automaticamente (FK `document_id`)
- `notes` funziona automaticamente
- `import_logs` funziona automaticamente
- Query dashboard/scadenziario funzionano senza modifica

### ✅ Estensione Rapida

Aggiungere un nuovo tipo richiede **solo**:
1. UPDATE CHECK constraint (1 query SQL)
2. ADD COLUMN per campi specifici (opzionale)
3. UPDATE modello Python
4. Implementa logica import/creazione

Tempo stimato: **< 1 giorno** per tipo documento complesso.

---

## Roadmap Tipi Documento

### Priorità Alta (Q1 2026)
- ✅ Fatture (completato)
- 🔜 F24 (schema pronto, implementare import PDF + OCR)
- 🔜 Assicurazioni (schema pronto, implementare gestione polizze)

### Priorità Media (Q2 2026)
- 🔜 MAV/CBILL (schema pronto, implementare import avvisi)
- 🔜 Affitti ricorrenti (schema pronto, generazione rate automatica)
- 🔜 Scontrini (schema pronto, import massivo + OCR)

### Priorità Bassa (Q3-Q4 2026)
- 🔜 Contratti di manutenzione
- 🔜 Utenze (luce, gas, acqua)
- 🔜 Pedaggi autostradali
- 🔜 Carburanti

---

Questo file va aggiornato man mano che si implementano nuovi tipi documento.
````

---

## ✅ RIEPILOGO MODIFICHE DOCUMENTAZIONE

### File Aggiornati

1. ✅ **docs/database.md** – completamente riscritto per riflettere supertipo `documents`
2. ✅ **docs/architecture.md** – sezione "Domain Model" aggiornata
3. ✅ **PROJECT_OVERVIEW.md** – sezione "Funzioni principali" aggiornata
4. ✅ **FUTURE_DOCUMENT_TYPES.md** – riscritto come implementation guide

---

## 🎯 Prossimo Step

**La documentazione è ora allineata al database.**

Vuoi che procediamo con:

1. **Aggiornamento modelli Python** (Document, InvoiceLine, Payment, ecc.)?
2. **Aggiornamento import_service.py** per usare `documents`?
3. **Script di test** per verificare il funzionamento?

Dimmi quale preferisci e lo preparo completo! 🚀