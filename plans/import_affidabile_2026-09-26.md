# Importazione affidabile — proposta del 26 settembre 2026

## 1) SPEC — Intento e vincoli

Stato: proposta da approvare prima dell'implementazione. Base letta: HEAD
`b6b4fb0`, inclusi naming e report recenti. Nessun dato operativo modificato.
Il rapporto diagnostico preesistente rimane intatto.

Obiettivo: un file accettato produce tutti i suoi documenti completi oppure
nessun nuovo documento; ogni tentativo conserva un esito o uno stato da
riconciliare. Una ripetizione restituisce gli ID esistenti oppure un conflitto
esplicito. File e MySQL NON costituiscono una transazione distribuita.

Fonti lette: AGENTS.md, docs/00_INDEX.md, docs/architecture.md,
docs/database.md, docs/guides/xml_storage_naming.md,
docs/fatturapa/PARSING_REFERENCE.md,
docs/diagnostics/fatture_perse_2026-09-26.md e relativo riproduttore.
Parser e presentazione restano nei rispettivi livelli; query nei repository,
orchestrazione nei servizi. Non cambiare config.py, schema, logging globale,
fatture originali o dati di produzione. Nessuna nuova dipendenza prevista.

### Flusso corrente verificato

Upload temporaneo o scansione -> selezione candidati XML/P7M -> precheck nome
-> hash file/batch -> parser v2 con fallback legacy -> copia annuale con nome
leggibile -> ciclo body: intestazione, fornitore, duplicati, documento, righe,
IVA, scadenze e DDT -> import_log success + commit PER BODY -> riepilogo ->
archiviazione originale -> CSV -> JSON/redirect e aggregazione browser.
Il parser restituisce più body; il difetto principale è nella persistenza.
Le note di credito seguono già regole specifiche per pagamenti/DDT da preservare.

### Evidenza e limiti

Riproduzioni rieseguite il 26 settembre: 11/11 con asserzioni attese.
Dieci esercitano il codice corrente; la numero 7 esegue esplicitamente la
funzione storica di salvataggio da Git e non dimostra un difetto del naming nuovo.
SQLite in memoria, DTO sintetici, directory temporanee, nessuna configurazione
di produzione. L'interprete disponibile è Python 3.14; il progetto indica 3.12.

Confermati sul codice corrente: copia orfana dopo commit fallito; copia aggiuntiva
per duplicato contabile; secondo body scartato per hash condiviso; stessa
denominazione file che blocca una diversa fattura; wildcard LIKE nel nome;
placeholder che impedisce retry; errore di archivio sommato al successo già
committato; log errore perso al termine della sessione. Confermati anche il
blocco corretto di byte identici rinominati e il percorso delete/reimport.

Rischi individuati ma NON ancora riprodotti su MySQL: concorrenza tra processi,
commit con risposta persa, crash reale e riavvio, perdita del deposito o del
log diagnostico durante l'operazione. Il confronto contabile iniziale omette
l'intestazione e rimuove separatori; il tipo TD originale non è conservato
integralmente in documents. Questi sono riscontri del codice, non cause provate
dei due episodi storici. La loro causa resta non accertata.

## 2) PLAN — Implementazione proposta

### A. Riutilizzo del registro MySQL, senza migrazione

Riutilizzare import_logs.message come JSON versionato per i nuovi record;
mantenere la lettura dei vecchi messaggi testuali. Una riga coordinatrice per
tentativo/file, document_id NULL, e righe success associate ai singoli body.
Non cambiare i valori ammessi dal CHECK: success/error/warning/duplicate.
Gli stati precisi sono nel payload, non nuovi valori della colonna status:

| Stato applicativo | status compatibile |
| --- | --- |
| started, staged, reconcile | warning |
| committed | success |
| duplicate | duplicate |
| conflict, failed | error |

Payload v1: attempt_id UUID, batch_id UUID, UTC, versione applicativa,
istanza, operatore disponibile, sorgente, nome originale, SHA-256, percorso
staging/finale, conteggio body, snapshot di identità per body, ID documenti,
fase/esito, codice e causa sanificata, criterio di duplicazione e ID esistente.
Usare import_source='attempt:<UUID>' per recuperare le righe di un tentativo;
la sorgente originale resta nel JSON e nei documents. Il campo non indicizzato
è un limite prestazionale dichiarato, non motivo per una migrazione preventiva.
La riga coordinatrice conserva gli ID storici e gli snapshot anche dopo delete.

Committare started separatamente PRIMA di modificare documenti. Il suo passaggio
a committed, tutti i nuovi documenti/dettagli e i success per body devono
avvenire nella stessa transazione InnoDB. Dopo rollback registrare failed in
una nuova transazione; se non disponibile restano started e il manifest.
Un commit incerto NON va riscritto come failed prima della riconciliazione.

### B. Serializzazione tra processi

Un lock MySQL nominato per database protegge import, recupero e cancellazione
dei file XML. È globale per semplicità: un file alla volta, non tutto il batch.
Acquisizione con timeout limitato; nessun fallback silenzioso a lock Python.
Sessione ORM vincolata alla STESSA connessione che possiede il lock fino al
rilascio esplicito. Nessuna riconnessione trasparente prosegue le scritture.
Adattare UnitOfWork con sessione opzionale, preservando il default degli altri
servizi; rendere esplicita la sessione del repository import_logs.

GET_LOCK sopravvive a commit/rollback e termina alla chiusura della sessione:
[riferimento MySQL](https://dev.mysql.com/doc/refman/8.4/en/locking-functions.html).
Questa protezione è cooperativa su un solo server MySQL: SQL esterno e vecchi
worker non aggiornati non sono coperti. Distribuzione con arresto dei vecchi
importatori, non deployment misto. Non si aggiunge un UNIQUE contabile senza
aver verificato le regole e le ambiguità dei dati storici.

### C. Protocollo per file e recupero

1. Assegnare ID batch/tentativo prima dell'elaborazione; tracciare anche errori
   di ricezione e file esclusi. Copiare l'input in staging persistente sotto
   il deposito; hashing e parsing devono leggere quella copia immutabile.
   Le sottocartelle upload separate conservano il nome originale senza
   rinominare arbitrariamente file omonimi. Se manca ogni destinazione durevole
   per la traccia, rifiutare l'accettazione prima delle scritture definitive.
2. Manifest versionato scritto mediante file temporaneo, flush/fsync e rename
   sullo stesso volume; directory e file privati del tentativo. Conservare
   l'originale recuperabile, non il solo percorso di un upload temporaneo.
3. Parsing completo e validazioni di tutti i body: numero, data, tipo,
   identità fiscali, righe e importi necessari alla persistenza. Identità
   ambigue o DTO incompleti producono conflitto/errore, mai nuovi placeholder.
   Registrare warning consentiti esplicitamente, senza azzerare totali mancanti
   per far sembrare completa una fattura. Verificare conteggio body XML/DTO.
4. Acquisire il lock, riconciliare tentativi precedenti pertinenti e verificare
   TUTTI i duplicati prima della pubblicazione. Anagrafiche nuove/modificate
   restano nella transazione del file; rollback se un body è in conflitto.
5. Preparare percorso annuale riservato al tentativo, per esempio
   ANNO/<attempt_id>/<nome-leggibile>.xml. Preservare il formato leggibile,
   estensione e suffisso _multi; nessuna rinomina dello storico. La directory
   UUID creata in esclusiva evita la corsa check-then-copy e la sovrascrittura
   di file altrui. Registrare il percorso nel manifest PRIMA di pubblicare.
6. Pubblicare dalla staging con rename sullo stesso volume dopo flush/fsync,
   riaprire e verificare hash. Conservare una copia di recupero fino alla
   finalizzazione. Scrivere tutti i dettagli e i log success; un solo commit.
7. Rispondere successo solo dopo commit confermato e file definitivo leggibile
   con hash atteso. Errore successivo di CSV, JSONL o archivio diventa avviso
   accessorio, mai 'non importato'. Se il definitivo manca dopo il commit:
   esito 'da riconciliare', ID visibili, recupero dalla copia persistente.
8. Archiviare l'originale con naming esistente, conservando nel manifest il
   percorso prenotato e verificando hash al retry. Non spostare/rimuovere un
   sorgente già referenziato da documents; non riprocessare staging/archivi.
9. Al riavvio/prima di nuovi import e tramite comando dedicato, acquisire il
   medesimo lock, leggere il registro sul primario con sessione fresca e
   confrontare manifesto, success per body, documenti e file. Se committed,
   restituire tutti gli ID e completare solo le operazioni accessorie. Se il
   vecchio lavoro è certamente terminato senza commit, marcare interrupted e
   permettere un nuovo tentativo collegato. Se DB/lock non sono disponibili,
   mantenere reconcile e non reinserire. Gli stati vecchi/incoerenti non si
   riparano per deduzione: esporre conflitto per revisione.
10. Nessuna cancellazione automatica di orfani nella prima versione: conservarli
    in staging/quarantena con motivazione e percorso. Ogni pulizia futura deve
    verificare proprietà, hash e assenza di riferimenti DB; mai basarsi sul nome.

Un crash può lasciare un file senza documento, ma deve lasciarlo riconoscibile
e recuperabile. Non promettere che fsync/rename garantiscano la persistenza
fisica del NAS: dipende da filesystem, mount e storage. DB e filesystem
ripristinati a date diverse richiedono riconciliazione, non retry automatico.

### D. Identità e duplicati

Identità operativa conservativa: fornitore fiscale (IdPaese+IdCodice, CF quando
pertinente), intestazione destinataria fiscale e applicativa, TipoDocumento
TD originale, numero e data. Non eliminare slash, trattini o zeri significativi;
non usare l'importo per distinguere due versioni della stessa identità.
Leggere IdPaese fiscale: non sostituirlo con il paese della sede anagrafica.
Conservare questi dati nello snapshot del log senza aggiungere colonne.
Ambiguità nelle anagrafiche e intestazione forzata incoerente: conflitto esplicito.

Il nome è informativo: stesso nome/contenuto diverso va analizzato. Stesso
hash identifica il contenitore, non un singolo body. Verificare il completamento
di tutti i body prima di classificare un file intero come duplicato.
Stessa identità e dati contabili equivalenti restituiscono il documento; stessa
identità con dati diversi o equivalenza non dimostrabile produce conflitto.
Confronto versionato dei dati parsati prima delle trasformazioni applicative:
non equiparare documenti solo perché il totale coincide. Per equivalenze XML
con byte diversi confrontare tutti i campi contabili gestiti; differenze non
interpretate rilevanti vanno riportate come conflitto conservativo.

Storico senza snapshot: leggere il file già collegato, identificare il body e
confrontare dati e identità. File mancante, tipo TD non ricostruibile o vecchio
placeholder: conflitto riconoscibile, senza modifiche/migrazioni automatiche.
Multi-body misto: body già presenti verificati e nuovi body sono riportati
separatamente; tutti i nuovi body si salvano insieme. Un conflitto annulla tutti
i nuovi inserimenti del file. Un hash associato soltanto al primo body storico
non deve impedire di rilevare l'incompletezza.

La preferenza XML/P7M omonimi resta solo se l'equivalenza è verificata;
altrimenti processare entrambi o mostrare conflitto, senza scarti silenziosi.
Tracciare i candidati esclusi e includere .XML nella scansione.

### E. Diagnostica, cancellazione e UI

Riutilizzare il formato JSON e gli helper esistenti con un canale import
dedicato, JSONL versionato su volume persistente, rotazione per istanza/processo
per evitare rotazioni concorrenti dello stesso file. Mount dedicato per
diagnostica e CSV in docker-compose.yml; default del logging generale invariati.
Ogni tentativo emette started e l'esito terminale o reconcile. Non includere
XML, credenziali, SQL con parametri né dati anagrafici non necessari.
Fallimento JSONL: avviso e registro MySQL/manifest; dopo commit non mutare l'esito.
Il JSONL è diagnostico e può avere lacune: non è atomicamente sincronizzato
con MySQL. Il registro MySQL è la prova del commit; il manifest permette il
recupero delle operazioni filesystem.

Delete: snapshot durevole con numero/data, identità fiscale, tipo, ID storico,
percorso/hash, operatore e motivo richiesto dalle due UI di cancellazione.
Audit e delete nella stessa transazione; un errore audit impedisce il delete.
I riferimenti multipli allo stesso XML impediscono la rimozione del file;
nessuna cancellazione di file durante il recupero degli import. Conservare
la traccia storica anche quando le FK diventano NULL.

Report HTML/JSON/CSV: una riga per body, raggruppata per file/tentativo, con
numero/data, fornitore, intestazione, nome, stato, motivo leggibile e link agli
ID esistenti. Distinguere contatori file/documenti e avvisi post-commit.
Conservare i dettagli recenti e aggiungere esiti conflict/reconcile.
Paginate/espandibili oltre 50 dettagli; aggregazione di tutti i batch e report.
In cookie/sessione solo ID riepilogo, non l'intero batch. Risposta HTTP persa:
mostrare stato incerto e recuperare per batch/tentativo, senza dedurre rollback.

### File previsti (percorsi completi)

- D:\Progetto_Database_Acquisti\app\services\import_service.py
- D:\Progetto_Database_Acquisti\app\services\import_recovery_service.py (nuovo)
- D:\Progetto_Database_Acquisti\app\services\unit_of_work.py
- D:\Progetto_Database_Acquisti\app\services\logging.py
- D:\Progetto_Database_Acquisti\app\services\document_service.py
- D:\Progetto_Database_Acquisti\app\repositories\import_log_repo.py
- D:\Progetto_Database_Acquisti\app\repositories\document_repo.py
- D:\Progetto_Database_Acquisti\app\parsers\fatturapa_parser.py
- D:\Progetto_Database_Acquisti\app\parsers\fatturapa_parser_v2.py
- D:\Progetto_Database_Acquisti\app\web\routes_import.py
- D:\Progetto_Database_Acquisti\app\web\routes_documents.py
- D:\Progetto_Database_Acquisti\app\templates\import\import_run.html
- D:\Progetto_Database_Acquisti\app\templates\documents\review.html
- D:\Progetto_Database_Acquisti\app\templates\documents\detail.html
- D:\Progetto_Database_Acquisti\app\static\js\import_batch.js
- D:\Progetto_Database_Acquisti\manage.py
- D:\Progetto_Database_Acquisti\docker-compose.yml
- D:\Progetto_Database_Acquisti\tests\test_import_lifecycle.py (nuovo)
- D:\Progetto_Database_Acquisti\tests\test_import_mysql.py (nuovo)
- D:\Progetto_Database_Acquisti\tests\test_import_storage_naming.py
- D:\Progetto_Database_Acquisti\tests\test_import_report.py
- D:\Progetto_Database_Acquisti\docs\guides\xml_storage_naming.md
- D:\Progetto_Database_Acquisti\docs\guides\import_recovery.md (nuovo)
- D:\Progetto_Database_Acquisti\docs\architecture.md
- D:\Progetto_Database_Acquisti\docs\00_INDEX.md

### Verifica pianificata e criteri di accettazione

Prima prove veloci isolate con XML sintetici e parser reale; quindi MySQL 8.0
InnoDB dedicato, Python 3.12 e processi indipendenti. Mai usare DB_NAME o
connessioni di produzione nei test. SQLite non certifica lock/commit MySQL.

| Iniezione/scenario | Asserzione necessaria |
| --- | --- |
| Errore validazione/flush/prima del commit | Nessun nuovo documento/dettaglio/success; fallimento durevole |
| Errore di commit con rollback noto | Stessa asserzione; retry crea una sola copia logica |
| COMMIT applicato ma ACK perso | Rilettura trova committed e tutti gli ID; nessun nuovo inserimento |
| Crash processo dopo pubblicazione e prima di commit | Nuovo processo riconcilia manifest e DB; nessuna perdita silenziosa |
| Crash dopo commit e prima di risposta | Recupero restituisce tutti gli ID e completa archivio |
| Deposito non disponibile, anche dopo commit | Mai falso successo; reconcile con ID se DB già committato |
| JSONL/CSV non scrivibili | Successo DB conservato, avviso diagnostico e recuperabilità |
| Retry e due processi contemporanei | Un solo insieme di documenti, secondo esito duplicate/conflict |
| Stesso nome/dati diversi; nome diverso/byte uguali | Nessun falso scarto e nessun duplicato silenzioso |
| XML equivalente, stessi dati/byte diversi | Duplicato per identità documentato, non per nome |
| Due destinatari, TD diversi, numeri A/1 e A1 | Nessun accorpamento arbitrario |
| Multi-body e guasto sull'ultimo body | Zero nuovi documenti se fallisce, tutti se riesce |
| Parziale storico/placeholder/file storico mancante | Conflitto esplicito oppure recupero dimostrabile, mai skip dell'intero file |
| Delete di un body con file condiviso | Altro documento ancora leggibile; audit e motivo superstiti |
| Riavvio/ricreazione container | Registro, staging e JSONL persistono; riepilogo recuperabile |
| Più batch e oltre 50 dettagli | Tutti gli esiti accessibili; contatori e link coerenti |

Comandi di base già eseguiti:

```text
python -W ignore::DeprecationWarning docs/diagnostics/reproduce_import_lifecycle.py -v
python -W ignore::DeprecationWarning -m unittest discover -s tests -p 'test_import*.py' -v
```

Risultati: 11 riproduzioni attese e 5 test naming/report passati. Il primo
tentativo nel sandbox è fallito per accesso alle directory temporanee; riesecuzione
con autorizzazione automatica riuscita. Non attribuire tali errori all'import.
I cinque test attuali sono baseline da adattare dove codificano il comportamento
errato; non sostituiscono la matrice sopra. Concorrenza e crash MySQL NON ancora
testati. Istruzioni CLI di recupero e comandi test definitivi saranno consegnati
con l'implementazione, non presentati ora come funzionalità disponibili.

## Punto di conferma

La proposta non richiede DDL, backfill o migrazione. Richiede però un refactoring
coordinato tra parser, repository, servizi, UI e gestione del deposito.
AGENTS.md, Safety stop: «wide refactors across layers» -> «STOP after SPEC + PLAN
and ask for confirmation before implementing».

IMPLEMENT e VERIFY della nuova soluzione restano da eseguire dopo la conferma.
In questa fase è stato creato soltanto questo piano; il codice applicativo e i
dati operativi non sono stati modificati.


## 3) IMPLEMENT — Aggiornamento del 28 settembre

Implementazione autorizzata dall'utente. Protocollo senza migrazione realizzato;
istruzioni e limiti in `docs/guides/import_recovery.md`. Conservazione prudente
anche delle sorgenti server e dei file dei documenti eliminati. Nessun deploy
né accesso al database operativo. L'utente ha confermato che MySQL di test non è
 disponibile e ha richiesto la consegna dei test da eseguire.

## 4) VERIFY — Riscontro

Verifiche locali con XML sintetici, factory Flask isolata, SQLite, fault injection,
processi realmente terminati e riavviati. Suite MySQL separata e opt-in, con
rifiuto degli schemi non vuoti o non denominati `test_import_*`. Vedere la guida
per i comandi, la matrice coperta e le verifiche ancora richieste sul deployment.
