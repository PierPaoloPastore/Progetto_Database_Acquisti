# Import affidabile e recupero

Aggiornamento: 28 settembre 2026. Nessuna migrazione dello schema.

## Garanzie e funzionamento

L'unità atomica MySQL è il file: anagrafiche, tutti i nuovi documenti, righe,
IVA, scadenze, DDT e conferma nel registro sono salvati con un solo commit.
Se un corpo è in conflitto o non è valido, nessun nuovo documento di quel file
viene salvato. Un batch può avere esiti diversi per file. I corpi già presenti
sono elencati individualmente; l'hash comune del file non nasconde gli altri.

Prima delle scritture contabili si registra il tentativo in `import_logs` e si
conserva l'input in `Deposito XML/.import-staging/<attempt_id>/`. Il manifest
versionato contiene fase, hash, percorsi, identità, batch e tentativo, operatore,
istanza e versione; il file originale resta separato, non dentro al log.
Gli upload vengono salvati direttamente qui, dopo la registrazione del tentativo.
Una ricezione troncata non genera un documento placeholder.

La copia definitiva usa `ANNO/<nome-leggibile>.xml` (o P7M).
La convenzione del nome leggibile introdotta il 26 settembre resta invariata.
Le copie identiche vengono riutilizzate; gli omonimi diversi ricevono un suffisso hash.
La copia originale viene conservata in `Archivio/XML/ANNO/<attempt_id>/<nome-originale>`.
Per import da cartella, Archivio resta nella cartella sorgente; per upload è nel
deposito. Gli originali sul server non vengono rimossi: potrebbero essere già
referenziati da altri documenti. Non si rinomina lo storico.

Il file definitivo viene copiato e verificato prima del commit, poi verificato
nuovamente prima di dichiarare successo. Un crash può lasciare un file orfano:
il manifest lo identifica, senza dedurre dal solo file che esista una fattura.
Un commit con risposta persa viene verificato con una connessione nuova, dopo
aver acquisito il lock che attende la fine del vecchio writer. Non si riprova
alla cieca. Se la verifica non riesce, l'esito resta `reconcile`.

Il lock MySQL è globale per database e condiviso da import, recupero e delete.
La sessione ORM usa la stessa connessione fisica del lock. Le tabelle coinvolte
devono essere InnoDB: il controllo viene eseguito prima delle scritture.
SQLite è ammesso soltanto con `TESTING=True`; non sostituisce i test MySQL.

## Duplicati e conflitti

Il nome da solo non blocca l'importazione. Anche XML/P7M omonimi vengono
analizzati; i file non riconoscibili come fatture producono un esito esplicito.
La scansione include `.XML` ed esclude Archivio, staging e diagnostica.

L'identità originale comprende identificativi fiscali di fornitore e destinatario,
IdPaese fiscale, tipo TD, numero e data. Il numero conserva slash, trattini e
zeri. L'intestazione applicativa viene verificata insieme all'identità XML.
Questa è una regola operativa conservativa, non un nuovo vincolo fiscale UNIQUE.

L'impronta di ogni corpo ignora indentazione e prefissi dei namespace, mantenendo
i campi anche non interpretati dal gestionale. Stessa identità e impronta uguale
restituiscono il documento; impronta differente o identificativi discordanti
richiedono revisione. Alcune equivalenze più complesse (per esempio diverse
rappresentazioni numeriche) possono essere segnalate come conflitto prudenziale.

Per i documenti vecchi privi dello snapshot versionato viene letto il loro XML.
Se il file o l'identità non sono verificabili, non si dichiara un duplicato certo.
Un file definitivo alterato viene segnalato; non viene sovrascritto dal recupero.

## Registro, diagnostica e conservazione

Si riusano `import_logs.message` per JSON v1 e gli status già ammessi:
`warning` per avvio, `success` per commit, `duplicate` per duplicato,
`error` per fallimento/conflitto. Il campo JSON `state` distingue gli esiti precisi.
Una riga coordinatrice per tentativo conserva tutti gli ID e gli snapshot; le
righe dei body collegano i success ai documenti. I vecchi log testuali restano leggibili.
`import_source=attempt:<UUID>` individua il tentativo; la sorgente originale è
nel JSON e nel documento.

Il registro MySQL prova il commit. JSONL e manifest NON sono sincronizzati
atomicamente con MySQL. Il JSONL è diagnostico; il manifest serve al recupero
dei file. Un errore JSONL o CSV non annulla un commit: produce un avviso.
Se MySQL e tutti i supporti di registrazione sono indisponibili, l'operazione
non viene accettata e non può garantire una traccia durevole del rifiuto.

`IMPORT_DIAGNOSTIC_DIR` sceglie la directory di JSONL e CSV; il fallback è
`.import-diagnostics` nel deposito. Il compose monta un volume dedicato in
`/var/lib/gestionale-import`. La staging è nel deposito e deve trovarsi sul
volume persistente già usato per gli XML. Non eliminare questi volumi durante
la ricreazione del container. Impostare `APP_VERSION` alla revisione distribuita;
se assente il registro riporta onestamente `unknown`.

JSONL separati per istanza/processo, rotazione 5 MiB con cinque copie.
La rotazione limita ogni processo, non la somma dei file di tutti i processi
storici. La conservazione complessiva va gestita operativamente. Nessuna pulizia
automatica di staging, XML, archivi o CSV è introdotta in questa versione.
Non sono registrati XML completi, credenziali o SQL con parametri nel nuovo registro.
L'operatore proviene dal middleware esistente, che attualmente è uno stub:
non equivale a un'identità autenticata e viene indicato come tale.

La cancellazione contabile richiede il motivo nella UI e salva audit + delete
nella stessa transazione. Numero, identità, operatore e motivo restano nel
payload quando la FK diventa NULL. I file vengono conservati, anche se nessun
documento li referenzia più, per non rimuovere XML condivisi o prove diagnostiche.

## Procedura di recupero

1. Verificare che database e deposito siano disponibili e che stia girando solo
   la nuova versione dell'applicazione. I vecchi worker non rispettano il lock.
2. Riaprire **Riapri l'ultimo tentativo** nella pagina import. Il batch è conservato
   anche nel browser prima dell'invio; `/import/run?batch_id=<UUID>` permette di
   ritrovare il riepilogo senza il cookie originale. `/import/status/<UUID>`
   restituisce lo stesso esito in JSON. Il cookie conserva solo l'ID.
3. Eseguire, nell'ambiente configurato del gestionale:

   ```sh
   python manage.py recover-imports
   ```

   Il comando riconcilia i tentativi pendenti sotto lock; viene richiamata la
   stessa procedura prima di nuovi batch. Non è un job periodico né un comando
   di reimportazione: non crea fatture, non cancella file e non avvia migrazioni.
   Controlla anche avvii registrati in MySQL prima della creazione del manifest.
4. Un commit confermato restituisce gli ID e completa l'archivio. Se manca un
   file definitivo di quel tentativo, la copia conservata viene ripubblicata
   dopo verifica dell'hash. Un file esistente diverso non viene sovrascritto.
5. Un tentativo certamente interrotto senza commit diventa `failed/INTERRUPTED`:
   ricaricare l'originale è sicuro. Se rimane `reconcile`, ripristinare accesso
   a DB/deposito e rieseguire il comando prima di decidere l'esito.
6. Per `conflict`, usare numero/identità e link del report per la revisione.
   Non cancellare fatture o file soltanto per superare un conflitto.

Le operazioni già finalizzate senza avvisi non sono riscansionate dal comando;
la pagina verifica comunque che i file dei documenti mostrati siano presenti
e abbiano l'hash registrato. Un danno successivo al deposito richiede diagnosi
e recupero mirato, non una nuova importazione automatica:

```sh
python manage.py recover-imports --attempt-id <UUID-del-tentativo>
```

## VERIFY — Verifiche e limiti

Ultima esecuzione locale, 28 settembre 2026: **23 test superati, 19 test MySQL
saltati** perché manca l'ambiente dedicato. Controlli sintattici Python e
JavaScript e `git diff --check` completati senza errori. Interprete locale:
Python 3.14; resta da verificare il deployment previsto con Python 3.12.

Prove locali: factory Flask con configurazione isolata, parser reale (in questo
ambiente il percorso xsdata ricade sul fallback legacy), SQLite su file temporaneo,
fatture sintetiche, errori iniettati e processi terminati con `os._exit`.
Copertura: commit fallito e ACK perso, crash prima/dopo commit e nuovo processo
di recupero, ultimo body fallito, retry/multi-body, destinatari e TD distinti,
stesso nome/dati diversi, XML equivalenti, file alterato o mancante, deposito e
diagnostica non disponibili, audit delete/file condiviso, report e route HTTP.

```sh
python -m unittest discover -s tests -p 'test_import*.py' -v
node --check app/static/js/import_batch.js
```

Per MySQL 8.0 usare uno schema VUOTO dedicato, con nome `test_import_*`, su un
server di prova. Impostare `IMPORT_TEST_MYSQL_URL` con le credenziali locali di
quel solo schema e poi eseguire:

```sh
python -m unittest discover -s tests -p 'test_import_mysql.py' -v
```

La suite rifiuta nomi diversi o schemi non vuoti. Crea e rimuove esclusivamente
le tabelle di prova in quel database. Ripete i guasti e avvia due processi
indipendenti: devono risultare un commit e un duplicato, con due documenti
totali per l'XML a due body. Non configurare mai l'URI operativo.

MySQL non è disponibile nell'ambiente locale: i test dedicati vengono saltati,
come concordato con l'utente. Non sono certificati qui concorrenza MySQL,
interruzioni di rete reali, durabilità del NAS o ricreazione del container.
Eseguire inoltre sul deployment di prova: due upload simultanei, riavvio del
container, oltre 50 dettagli, interruzione della risposta browser e riapertura
del batch. Verificare persistenza di registro, staging, JSONL e CSV.

Non esiste atomicità assoluta fra MySQL e filesystem. Le garanzie dipendono da
InnoDB, unico server MySQL, worker cooperanti e filesystem che rispetti flush,
fsync e rename. Ripristini DB/filesystem a date diverse, SQL esterno e cancellazioni
manuali richiedono riconciliazione. L'identità resta in JSON senza indici nuovi:
le ricerche dello storico sono lineari; batch con moltissimi body sono inoltre
limitati dalla capacità TEXT del registro esistente. Errori di capacità producono
rollback e traccia, non successi parziali.

### Riutilizzo del deposito definitivo

I nuovi import non creano sottocartelle per tentativo nel deposito annuale.
Prima della copia cercano contenuto identico (dimensione e SHA-256) nello stesso
anno, incluse le sottocartelle storiche: il nuovo record riutilizza il percorso
esistente e il report lo segnala. Un nome già occupato da contenuto diverso
riceve un suffisso SHA-256. Nessun file storico viene spostato o cancellato.
Archivio e staging mantengono gli identificativi tecnici per il recupero.
La scansione è lineare sui file dell’anno; per depositi molto grandi servirà
un indice degli hash. La lettura fallita di un candidato blocca il singolo import
anziché assumere che non esista una copia.
