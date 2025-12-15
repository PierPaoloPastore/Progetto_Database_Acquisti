# 6-Chat Workflow Runbook

Questo runbook documenta il flusso di lavoro a 6 chat utilizzato dal team. Ogni ruolo è sequenziale: **INTAKE → CAPO PROGETTO → PLANNER → PROMPT WRITER → REVIEWER → COMPOUNDER**. Usa le sezioni qui sotto come guida rapida, con template pronti da copiare/incollare.

## Flusso di lavoro
1. **INTAKE** – Riceve la richiesta, chiarisce ambiguità e raccoglie vincoli.
2. **CAPO PROGETTO** – Definisce obiettivo, vincoli e criteri di accettazione ad alto livello.
3. **PLANNER** – Traduce l'obiettivo in un piano di lavoro a passi chiari.
4. **PROMPT WRITER** – Prepara i prompt/brief operativi per gli esecutori.
5. **REVIEWER** – Verifica coerenza, copertura e rischi; suggerisce correzioni.
6. **COMPOUNDER** – Unifica output, esegue refinement finale e produce il deliverable.

## Template per ogni fase (copia/incolla)
### 1) INTAKE
```
Ruolo: INTAKE
Richiesta utente:
- [riassunto breve]
Domande di chiarimento / Assunzioni:
- [domanda o assunzione]
Vincoli noti (tecnici/tempi/ambito):
- [vincolo]
Prossimi passi:
- Passare a CAPO PROGETTO con il contesto sopra.
```

### 2) CAPO PROGETTO
```
Ruolo: CAPO PROGETTO
Obiettivo dichiarato:
- [goal sintetico]
Vincoli e scope:
- [scope, fuori scope]
Criteri di accettazione (DoD):
- [punti verificabili]
Risorse/artefatti disponibili:
- [link o file]
Prossimi passi:
- Passare a PLANNER con obiettivo e DoD.
```

### 3) PLANNER
```
Ruolo: PLANNER
Obiettivo ricevuto:
- [goal]
Piano operativo (passi ordinati):
1. [step]
2. [step]
Rischi e mitigazioni:
- [rischio → mitigazione]
Dipendenze/bisogni:
- [dipendenza]
Prossimi passi:
- Passare a PROMPT WRITER con il piano approvato.
```

### 4) PROMPT WRITER
```
Ruolo: PROMPT WRITER
Input (obiettivo + piano):
- [riassunto]
Prompt/brief operativi per esecutori:
- [istruzione concreta]
Formati/output attesi:
- [file, API, test]
Note di stile o policy:
- [linee guida]
Prossimi passi:
- Passare a REVIEWER con prompt e formati.
```

### 5) REVIEWER
```
Ruolo: REVIEWER
Materiale ricevuto:
- [piano, prompt]
Checklist di revisione:
- Coerenza con obiettivo e DoD
- Copertura di tutti i passi
- Rischi indirizzati
- Ambiguità o conflitti
- Aderenza a policy/stile
Esiti e correzioni:
- [OK / correzioni richieste]
Prossimi passi:
- Passare a COMPOUNDER con feedback incorporato.
```

### 6) COMPOUNDER
```
Ruolo: COMPOUNDER
Input finale (piano + prompt + revisioni):
- [riassunto]
Azioni di sintesi/esecuzione:
- [integrazione contenuti]
Deliverable prodotto:
- [output finale]
Verifiche finali:
- [test, check qualità]
Hand-off:
- [note per stakeholder o esecutori]
```

## Checklist "one-page" per l'intero flusso
- [ ] **INTAKE**: richiesta compresa? domande aperte annotate? vincoli raccolti?
- [ ] **CAPO PROGETTO**: obiettivo chiaro? DoD definito? scope/out-of-scope espliciti?
- [ ] **PLANNER**: piano passo-passo? rischi e mitigazioni elencati? dipendenze note?
- [ ] **PROMPT WRITER**: istruzioni operative concrete? formati/output attesi specificati? policy di stile incluse?
- [ ] **REVIEWER**: controlli su coerenza, copertura, rischi e policy? feedback documentato?
- [ ] **COMPOUNDER**: output integrato e rifinito? verifiche finali eseguite? hand-off completo?

Usa questa checklist come promemoria rapido prima di chiudere il ciclo.
