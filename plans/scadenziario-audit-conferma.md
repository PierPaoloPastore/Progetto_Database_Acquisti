# Scadenziario: audit e conferma dopo la generazione

Data: 2026-11-06.

## SPEC — Intento e vincoli

`Programmata` significa che l'estratto conto è stato stampato e le fatture sono
in attesa di pagamento. La sola generazione del PDF non autorizza la marcatura.
Il browser non certifica la stampa su carta: la conferma è una dichiarazione
esplicita dell'operatore.

Riutilizzare `document_audit_logs`, Repository e Unit of Work; nessuna migrazione,
modifica di config.py o dei default di logging. Non azzerare i flag storici.
Consultati docs/00_INDEX.md, docs/architecture.md, docs/database.md,
docs/guides/payments_ui.md e docs/meta/agents.md.

## PLAN — Approccio

1. Generare il PDF con un riferimento univoco. Registrare snapshot delle fatture,
   hash SHA-256, origine HTTP, sessione, postazione e identità disponibile.
2. Mostrare in un modal la tabella ricavata dallo snapshot del PDF e l'anteprima
   PDF opzionale. Download e chiusura non programmano fatture.
3. Richiedere verifica esplicita e conferma dopo la stampa. Un token firmato,
   legato alla sessione e valido due ore per la conferma, identifica la
   generazione salvata. È possibile annullare anche una conferma ormai scaduta.
4. Confermare esattamente lo snapshot generato: rifiutare documenti mancanti,
   saldati o modificati; salvare flag e audit nella stessa transazione.
5. Bloccare le conferme ripetute mediante l'esito della generazione, protetto da
   lock. Un vecchio token non deve riprogrammare dopo una rimozione del flag.
6. Registrare fallimenti PDF, chiusura esplicita e rimozione del flag.
7. Selezionare con le checkbox; nessuna selezione tramite clic generico sulla riga.
8. Aggiornare storico, guida e test isolati.

File coinvolti (radice `D:\Progetto_Database_Acquisti`):

- plans/scadenziario-audit-conferma.md
- app/services/schedule_service.py
- app/repositories/document_audit_log_repo.py
- app/repositories/document_repo.py
- app/services/document_service.py
- app/web/routes_payments.py
- app/web/routes_help.py
- app/static/js/schedule.js
- app/templates/payments/schedule.html
- app/templates/payments/schedule_print.html
- app/templates/documents/audit.html
- tests/test_schedule_workflow.py
- tests/test_schedule_workflow.cjs

Rischi e mitigazioni:

- Audit e flag devono fallire insieme: nessuna marcatura se il salvataggio audit
  fallisce. Le conferme concorrenti bloccano la riga della generazione e poi i
  documenti in ordine di ID.
- Lo snapshot della generazione rimane nel payload originale; esito, data di
  chiusura e richiesta di chiusura completano il ciclo di vita. Le transizioni
  dei singoli documenti hanno eventi separati.
- Le modifiche fra generazione e conferma richiedono un nuovo PDF; non applicare
  la conferma a una selezione nuova o a un sottoinsieme silenzioso.
- L'utente corrente è `CurrentUserStub`: registrare questa provenienza senza
  presentarla come identità autenticata dell'operatore.

## IMPLEMENT — Comportamento e tracciabilità

Azioni audit: `schedule_gen`, `schedule_confirm`, `schedule_cancel`,
`schedule_unmark`, `schedule_failed`, `schedule_item`. Gli snapshot sono salvati
uno per fattura e collegati alla generazione, per non saturare il campo TEXT
con un singolo payload grande. Tutte le azioni rientrano nei 16 caratteri della
colonna esistente. Il riferimento dell'estratto compare anche nel PDF e nei log
JSON applicativi. Lo storico permette di espandere le fatture del PDF.
Le date dello storico sono esplicitamente indicate in UTC.

Importazione e revisione non scrivono `print_status` nel codice attuale. Il
salvataggio dei documenti non è un evento di creazione dell'estratto conto.
Un ripristino esterno del database può sostituire anche l'audit: il codice web
non può intercettarlo. Per indagini su restore conservare separatamente log,
binlog e cronologia dei backup, prima di ripristinare. I log applicativi
seguono la rotazione esistente e non sono un archivio permanente garantito.

Un modal abbandonato chiudendo la scheda o un download interrotto lascia una
generazione in attesa di conferma: nessun flag viene modificato. L'annullamento
esplicito dal modal registra invece un esito di annullamento.

## VERIFY — Validazione

- Test backend con Flask e SQLite in memoria, senza configurazione o dati reali.
- Test JavaScript con Node e DOM simulato per il flusso generazione/conferma.
- Verificare: nessun flag dopo generazione/download/annullamento; conferma della
  sola lista del PDF; token alterati, scaduti o di altra sessione respinti;
  fatture cambiate respinte; replay innocuo; audit e flag atomici.
- Manuale: selezionare fatture in più intestatari, verificare che tutte compaiano
  nel PDF, stampare e confermare. Consultare Storico documenti e confrontare il
  riferimento con quello nel PDF. Ripetere chiudendo senza conferma e usando
  `Togli programmata`.
- Verificare la concorrenza su MySQL in ambiente di collaudo: SQLite non simula
  i lock di riga MySQL. Non usare il database operativo per questi test.

### Esito locale

- `python -B -m unittest discover -s tests -p test_schedule_workflow.py -v`:
  13 test superati.
- `node tests/test_schedule_workflow.cjs`: superato.
- `node --check app/static/js/schedule.js` e `git diff --check`: superati.
- Collaudo nel browser con SQLite in memoria e dati fittizi: chiusura senza
  marcatura, modal con lista esatta, conferma esplicita, comparsa del badge e
  storico di generazione/annullamento/conferma verificati.
- Il motore PDF non è disponibile nell'ambiente locale: il collaudo UI usa un
  PDF di prova. Non verificati qui il rendering PDF effettivo e i lock MySQL.
- Nessun accesso al database operativo; flag storici invariati.

## Correlazione HTTP e audit — 2026-11-07

Ogni POST a `schedule/print`, `schedule/preview`, `schedule/confirm`,
`schedule/cancel` e `schedule/unprogram` riceve un nuovo `request_id` generato
dal server. L'header di risposta `X-Request-ID` permette di ritrovarlo dagli
strumenti di rete del browser. Un eventuale `X-Request-ID` del client non viene
riutilizzato. L'ID identifica una singola richiesta, mentre `schedule_id`
collega generazione e conferma dello stesso estratto.

Il payload JSON esistente di `document_audit_logs` conserva in `actor`:
`request_id`, `method`, `path`, `endpoint`, `handler` (funzione Flask),
`ui_action`, oltre a sessione, IP, user agent e identità già presenti.
La generazione conserva il proprio `actor`; `closed_by` identifica la richiesta
di conferma o annullamento. Le righe `schedule_confirm` e `schedule_unmark`
contengono direttamente la richiesta che ha cambiato il flag. Nessuna migrazione
o modifica dello schema DB.

Il JavaScript dichiara l'azione nell'header `X-Schedule-Action`:

| Etichetta | Origine in `app/static/js/schedule.js` |
| --- | --- |
| `schedule.generate` | azione bulk `print`, form `schedule-print-form` |
| `schedule.preview` | richiesta della lista del PDF appena generato |
| `schedule.confirm_print` | `finishPreview(true)`, pulsante di conferma stampa |
| `schedule.cancel` | `finishPreview(false)`, chiusura senza programmare |
| `schedule.unprogram` | azione bulk `unprogram`, pulsante Togli programmata |

`ui_action` è un'etichetta dichiarata dal client, non prova di un clic fisico.
Viene salvata solo se corrisponde all'etichetta prevista per l'endpoint;
altrimenti è `null`. I client senza l'header continuano a funzionare.
Metodo, percorso, endpoint e handler sono ricavati dal server. Non si salvano
body, query string, token, cookie o header di autorizzazione.

I log JSON delle operazioni hanno lo stesso ID in `extra.request_id` e in
`extra.actor.request_id`. Un evento `extra.schedule_event = http_request`
registra anche lo stato HTTP della risposta, inclusi rifiuti e tentativi
ripetuti che non generano una nuova modifica. Lo storico documenti mostra
richiesta, metodo/percorso, endpoint, funzione e l'eventuale azione UI dichiarata;
gli eventi precedenti senza questi campi restano leggibili.

Per indagare un documento, leggere i payload dei suoi eventi:

```sql
SELECT id, document_id, action, created_at, payload
FROM document_audit_logs
WHERE document_id = 123
  AND action IN ('schedule_confirm', 'schedule_unmark')
ORDER BY id DESC;
```

Sostituire `123` con l'ID da verificare; cercare `actor.request_id` nei log
applicativi. Nei binlog, l'inserimento audit e l'aggiornamento del flag
appartengono alla stessa transazione. Il nuovo tracciamento vale dalle richieste
gestite dalla versione aggiornata, senza ricostruire i dati HTTP storici.

Validazione locale dell'estensione: 15 test backend con SQLite in memoria e
test JavaScript superati; sintassi JavaScript e `git diff --check` verificati.
Coperti correlazione audit/log/header, ID distinti, replay, rifiuti, errore PDF,
azioni UI, esclusione dei segreti e compatibilità degli audit precedenti.
Nessun accesso a MySQL operativo o lettura dei binlog durante la verifica.
