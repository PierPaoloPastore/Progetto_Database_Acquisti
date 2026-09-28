# Fatture perse: indagine approfondita del 26 settembre 2026

## Stato dell'indagine

Codice esaminato: `b6b4fb0`, confrontato con `86b5197` e il ramo storico di luglio.
Esaminati documentazione, importazione, repository, transazioni, cancellazioni, naming,
report e visibilità. Letti in sola lettura otto XML reali dalla condivisione indicata.
Eseguite 11 riproduzioni isolate con SQLite in memoria e file temporanei.
Nessuna modifica a codice applicativo, DB operativo o XML originali.

**La causa storica dei due casi non è ancora accertata.** Il primo giro MySQL è stato
ricevuto dall'utente il 26 settembre; l'aggiornamento in fondo distingue i nuovi fatti
da ciò che resta da verificare. Le sezioni iniziali descrivono l'analisi precedente ai risultati.
Sono invece accertati i comportamenti riproducibili sotto elencati.
La presenza delle copie nel deposito non è prova sufficiente né di un commit né di una cancellazione.
Le copie presenti anche in Archivio/XML rendono necessaria un'indagine sullo storico,
non soltanto sui filtri dello scadenziario.

## 1. Evidenze reali: contenuto, nomi, date

Base letta: `\\192.168.1.111\Aziende_Pastore\Amministrazione\Acquisti\Gestionale Fatture Passive\Deposito XML`.
Le date seguenti sono CreationTimeUtc esposte dal filesystem SMB; non sono audit applicativi.
Copia, ripristino, migrazione o manipolazione esterna possono alterarne l'interpretazione.

| Caso | File | Creazione in 2026 (UTC) | Creazione in Archivio/XML/2026 (UTC) |
| --- | --- | --- | --- |
| Marcantuono | IT08567210961_y3R4F.xml | 18 luglio 07:58:32 | 18 luglio 07:58:33 |
| Marcantuono | IT08567210961_y3R4F_1.xml | 25 luglio 08:58:43 | 25 luglio 08:58:44 |
| Buoninfante | SM03473_GeaXw.xml | 7 luglio 10:12:11 | 7 luglio 10:12:13 |
| Buoninfante | SM03473_GeaXw_1.xml | 10 settembre 09:58:53 | 10 settembre 09:58:53 |

Per ciascun caso tutte e quattro le copie sono identiche byte per byte, compreso il file archiviato.
Sono XML leggibili senza errori di sintassi, ciascuno con **un solo FatturaElettronicaBody**.

| Campo | Marcantuono | Buoninfante |
| --- | --- | --- |
| Numero | 0003521-I | 1/2351 |
| Data | 2026-06-30 | 2026-06-30 |
| Tipo XML | TD01 | TD24 |
| Totale | 400,59 | 1.959,54 |
| Fornitore | MARCANTUONO S.R.L. | ALFREDO BUONINFANTE & C. SPA |
| P.IVA fornitore | 02305140655 | 02106670652 |
| Intestatario XML | LA FASANARA DI PASTORE M.E C. SRL | PASTORE MARIO |
| P.IVA intestatario | 04026780652 | 03185040650 |
| Dimensione | 839.682 byte | 5.086 byte |

SHA-256 Marcantuono:
`84dfd8eb6d2d80e5301f4464315c336d4b337b734297e621cb0c7eaa4c8b0f4d`

SHA-256 Buoninfante:
`9e019ba2439866014fa08e1222eb1e623e57f0defbe9a6e893b848ad2295836c`

La copia Buoninfante `_1` coincide temporalmente con la creazione MySQL indicata dall'utente
(10 settembre 09:58:54), non con l'updated_at del 24 settembre. La prima copia risale però a luglio:
serve verificare quale evento corrisponda al primo passaggio, e se esistesse un precedente record.
Non si può dedurre da queste date che il 24 settembre sia avvenuta una nuova registrazione.
Il prefisso IT08567210961 del file Marcantuono non coincide con la P.IVA del cedente:
per l'identità fiscale va usato il contenuto XML, non il nome trasmesso.

## 2. Documentazione contro codice

La guida `docs/guides/xml_storage_naming.md` descrive correttamente due copie e due ruoli.
Il naming leggibile del 26 settembre riguarda solo nuovi salvataggi dopo distribuzione sul server;
non rinomina lo storico. Le copie di luglio/settembre precedenti non sono causate da tale aggiornamento.

La descrizione "commit/rollback per file" in `docs/architecture.md` è imprecisa per XML multipli:
il codice esegue commit dentro il ciclo sui body. Non esiste inoltre una transazione comune
fra filesystem e MySQL. `shutil.copy2` avviene PRIMA della scrittura definitiva in DB.

I test naming esistenti simulano il repository; il caso multi-body controlla il nome `_multi`,
non che ogni fattura nel file sia davvero salvata. Le riproduzioni aggiunte usano repository
e sessioni reali, pur simulando il parser con DTO per isolare il ciclo di persistenza.

## 3. Il ciclo che decide se esiste una fattura

1. Salvataggio temporaneo dell'upload, eventuale suffisso se nomi uguali nel caricamento.
2. Selezione dei file: esclusione metadati, preferenza XML rispetto al P7M omonimo.
3. Controllo del nome in documents: può fermare il flusso prima di leggere il contenuto.
4. SHA-256 del file: confronto con hash già incontrati nel batch e import_logs collegati a documents.
5. Parsing. Se fallisce, tentativo di documento incompleto in revisione.
6. Copia nel deposito annuale, con suffisso se la destinazione esiste.
7. Creazione/ricerca anagrafiche; controllo contabile duplicati; creazione documento e dettagli.
8. Inserimento import_log success e COMMIT della stessa sessione DB.
9. Registrazione del successo nel riepilogo, poi spostamento dell'originale in Archivio/XML.

I duplicati riconosciuti ai punti 3–4 non generano una nuova copia annuale.
Quelli riconosciuti al punto 7 arrivano quando la copia è già stata prodotta.
Nel codice attuale possono terminare con log duplicate e archiviazione senza nuovo documento.
Prima del 23 settembre il log postcheck skipped poteva invece violare il CHECK e interrompere
l'archiviazione: possibile copia nel deposito senza nuovo log DB e senza nuovo originale archiviato.

## 4. Risposte ai tre dubbi, con prove

### Una fattura può sparire ed essere reimportata?

Sì, dopo una cancellazione vera, un reset, un ripristino ad altro stato o lavorando su un DB diverso.
Il percorso di eliminazione applicativo elimina documents e prova a cancellare il file indicato
da file_path; conserva l'originale in Archivio/XML. Le FK dei log sono previste ON DELETE SET NULL.
Al successivo import i controlli possono non trovare più alcun documento e consentire il nuovo inserimento.
Riprodotto: cancellazione esplicita, vecchio success scollegato, audit delete, nuova importazione e
`originale_1.xml` in Archivio/XML.

**Non è stato trovato un processo automatico che cancelli fatture dopo 14 giorni.**
Esistono due route POST di cancellazione e un'inizializzazione esplicita che tronca le tabelle.
Trigger, eventi, job, restore e SQL esterno sul server non sono verificabili dalla sola codebase.

Attenzione: una normale cancellazione applicativa dovrebbe anche rimuovere la copia annuale collegata.
Il fatto che esistano ancora entrambe le copie annuali nei casi reali richiede una spiegazione aggiuntiva:
file originario non collegato, errore di rimozione, cancellazione SQL/restore, copie esterne, o altro percorso.
Non basta quindi dire "è stato cancellato" senza audit e riscontro del vecchio file_path.

### Una fattura può essere caricata ma non registrata in MySQL?

Sì. Riprodotto un errore dopo la creazione/flush del documento e prima del commit:
zero documents e zero import_logs persistiti, ma copia XML nel deposito; il nuovo tentativo
crea il suffisso `_1` e registra una sola fattura. Interruzione processo o vincolo DB possono
produrre uno stato analogo, a seconda del punto di interruzione.

Nel normale percorso **success viene comunicato dopo il commit**, e documento + log success
sono nella stessa transazione. Con tabelle transazionali InnoDB, un success persistito non dovrebbe
coesistere con la mancata registrazione iniziale del documento. Un success oggi scollegato richiede
un evento successivo o una differenza di schema/istanza. Q1 e Q5 controllano questi presupposti.

Un errore nell'archiviazione finale, invece, avviene DOPO il commit: riprodotto un riepilogo con
1 importata + 1 errore e fattura ancora presente dopo la fine della richiesta.
La scritta generale "Import completato" o "Errore batch" non definisce da sola l'esito di ogni file.

### Può essere naming?

Sì, ma occorre distinguere i livelli:

- `_1` è un contatore di collisione su disco, non il numero delle importazioni DB.
- Con il salvataggio precedente al 26 settembre, importare per la prima volta un XML che è già nella
  destinazione annuale crea subito `_1`: riprodotto eseguendo la funzione storica reale.
- Nomi diversi e byte diversi per la stessa fattura possono creare un'altra copia prima del controllo
  contabile: riprodotto 2 copie, 1 documento, secondo esito skipped.
- Stesso nome per contenuti/fatture diversi: il secondo file viene scartato prima del parsing.
  Riprodotto con due numeri diversi. È mancata importazione, non cancellazione successiva.
- La LIKE del confronto multi-body tratta `_` e `%` come jolly: riprodotto un falso match
  fra `SM_ABC.xml` e `SMXABC.xml#body1`.
- Rinominare soltanto un XML identico non basta normalmente a reimportarlo: il suo hash lo blocca.
  Riprodotto 1 documento e 1 copia annuale dopo il secondo upload con nome diverso.

**Per i due casi reali, gli hash identici rendono insufficiente la spiegazione "ha cambiato nome"**,
se il primo import_log con quell'hash era presente e collegato a un documento nello stesso DB.

## 5. Difetti confermati e loro pertinenza

| Comportamento riprodotto | Conseguenza | Pertinenza ai due casi |
| --- | --- | --- |
| Copia prima del commit | Orfano sul filesystem, suffisso al retry | Possibile; da solo non spiega due coppie complete deposito/archivio |
| Copia prima del controllo contabile | Seconda copia senza seconda fattura | Possibile in generale; hash reali uguali richiedono che il precheck hash non trovasse il primo documento |
| Hash comune ai body multipli | Seconda fattura scartata come duplicato della prima; retry bloccato dal nome | Escluso per gli otto XML esaminati: un solo body |
| Documento placeholder dopo errore parser | Fattura non ricercabile per numero/fornitore; nuovi tentativi bloccati | Possibile storicamente con altro parser; XML attuali validi non dimostrano il vecchio esito |
| Nome prevale sul contenuto | Falso duplicato di una fattura diversa | Non osservato nei file esaminati, identici per coppia |
| Errori non sempre committati in import_logs | DB privo del log di un tentativo fallito | Confermato; log vuoto non prova che non ci sia stato un tentativo |
| Filtri memorizzati e ricerca letterale | Documento presente ma non visibile | Già riprodotto il 24 settembre; non spiega le seconde copie su disco |

La persistenza degli errori è particolarmente importante: `_log_error_db` non inserisce import_logs;
altri errori li aggiungono alla sessione ma non eseguono commit autonomo. Un errore finale può quindi
restare solo nel CSV/log testuale; un commit successivo può invece salvare un errore precedente.
Riprodotto il caso del log error perso alla chiusura della sessione e quello dell'errore archiviazione
non persistito mentre il success precedente rimane.

## 6. Ulteriori fattori verificati nel codice, senza attribuzione all'episodio

- Il lock import è per processo, non distribuito; il controllo non sostituisce un vincolo DB.
  Anche ensure_unique_filename fa check-then-copy: import concorrenti fra processi non hanno una
  prenotazione atomica del nome. Verificare deployment e vincoli, non dedurre concorrenza dai suffissi.
- Identità contabile: normalizzazione del numero elimina separatori e il primo confronto non usa
  legal_entity_id. Possibili falsi duplicati; non elimina un documento già salvato.
- Il set hash del batch viene aggiornato prima del successo: una seconda copia nello stesso batch
  può essere saltata anche se il primo tentativo fallisce.
- Un errore interrompe i successivi body di quel file; i commit precedenti sono già completati.
- Upload con più richieste: i batch precedenti possono essere committati anche se uno successivo fallisce.
- Il browser mostra solo i primi 50 dettagli e l'aggregazione upload non riporta i report_path dei singoli
  batch. Il CSV usa timestamp al secondo e può essere sovrascritto da un altro report con lo stesso nome.
- Il riepilogo dell'ultimo import è in sessione browser, non una cronologia completa di importazione.
- Scansione server: esclude tutte le directory chiamate Archivio; su Linux `*.xml` non include `.XML`.
  File XML/P7M omonimi sono ridotti a un candidato. File selezionato, file processato e fattura salvata
  non sono contatori intercambiabili.
- Cancellare un documento che condivide file_path con altri può rimuovere il file utilizzato da questi:
  `_remove_document_files` non verifica altri riferimenti. I loro record DB restano, ma l'anteprima fallisce.
- Modifiche manuali a numero/fornitore/intestatario o is_paid possono alterare ricerche e scadenziario;
  non implicano perdita della riga DB. La ricerca globale ha un limite diverso dallo scadenziario.
- Manca una cronologia completa con operatore, identificativo tentativo, commit, cancellazione e files:
  l'audit corrente non basta a ricostruire ogni operazione; serve incrociare più fonti.

## 7. Verifiche MySQL richieste e interpretazione

Primo giro in `fatture_perse_01_riscontri.sql`, Q1–Q5, tutte di sola lettura:
istanza/motori; record attuali; log per nome e SHA-256; audit inclusi payload dei cancellati; vincoli reali.
Per difficoltà di esecuzione si possono eseguire prima i SELECT semplificati riportati in conversazione.

| Risultato | Interpretazione e prossimo passo |
| --- | --- |
| Due success dello stesso hash verso due ID ancora presenti | Doppia registrazione, controllare versione/periodo/concorrenza e anagrafiche |
| Vecchio success con document_id NULL, poi nuovo success | Collegamento perso dopo un primo import; audit e FK possono individuare cancellazione |
| Audit delete con snapshot del primo documento | Prova del percorso di cancellazione registrato; non identifica automaticamente l'operatore |
| Un solo success recente, nessun log vecchio | Primo file non prova commit; considerare restore/reset/log mancanti/DB diverso e consultare backup |
| Vecchio warning, numero/fornitore mancanti | Placeholder, non fattura completa; esaminare note e versione parser |
| Documento unico creato al primo evento e log duplicate successivo | Elaborazione ripetuta senza nuova fattura; verificare perché il precheck non l'ha fermata |
| Documento presente ma is_paid true | Assenza dallo scadenziario per stato, da distinguere dalla duplicazione filesystem |

Se necessario il secondo giro riguarderà backup precedenti agli eventi (7/18/25 luglio, 10 settembre),
trigger/eventi DB e access log delete/initialize-db, non una scansione indiscriminata di tutti i dati.
L'assenza di righe in information_schema può dipendere anche dai privilegi.

## VERIFY — Riproducibilità

Comando: `python docs/diagnostics/reproduce_import_lifecycle.py -v`.
Risultato il 26 settembre: **11 prove completate con le asserzioni attese**.
Sono riproduzioni del comportamento attuale, comprese anomalie, non certificazione di correttezza.
Le prove usano sessioni/repository reali su SQLite; il parser è sostituito da DTO fittizi.
La chiave BIGINT audit è adattata a INTEGER soltanto nello schema effimero SQLite.
Il test storico estrae via Git solo `_store_import_file` dalla revisione `86b5197`.
Non sono riproduzioni dei vincoli/trigger/isolamento della produzione MySQL.

Conclusione aggiornata: i suffissi non dimostrano fatture perse, ma le quattro copie identiche per caso
e le date dei due passaggi meritano una ricostruzione DB. Non attribuire la responsabilità all'operatore,
non classificare tutto come filtro e non usare ulteriori reimportazioni come test diagnostico.

## 8. Primo giro MySQL: risultati forniti dall'utente il 26 settembre

L'utente ha eseguito il primo file SQL completo: la numerazione riportata separa
istanza e motori, pertanto non coincide con i quattro SELECT semplificati in conversazione.
Risultati interpretati per colonne/contenuto, non soltanto per numero.

### Fatti acquisiti

- Schema `gestionale_acquisti`, host MySQL `0a117854a5fb`, porta 3306; fuso SYSTEM/UTC,
  NOW e UTC_TIMESTAMP coincidono. Il fuso UTC conferma la comparabilità con le date SMB UTC.
- documents, import_logs e document_audit_logs sono InnoDB.
- Marcantuono: unico candidato pertinente ID **775**, creato **25 luglio 08:58:45**;
  numero `0003521-I`, totale 400,59, fornitore 41, intestatario 1 (P.IVA XML coincidenti).
  file_path `2026/IT08567210961_y3R4F_1.xml`; imported_at **NULL**;
  registration_date 25 luglio, due_date 30 settembre; verified, not_printed, is_paid 0.
  updated_at **31 luglio 09:56:43**.
- Marcantuono: unico success trovato, log **762**, **25 luglio 08:58:45**, collegato a 775
  e all'hash reale. Nessun vecchio success del 18 luglio, neppure scollegato, nei risultati.
- Audit **745** del **25 luglio 09:09:24**: documento 775 già collegato a `_1.xml`;
  modifica registration_date da NULL al 25 luglio e doc_status da pending_physical_copy a verified.
  Nessun delete pertinente restituito. L'audit non include imported_at né updated_at.
- Buoninfante: unico candidato pertinente **924**, creato/importato **10 settembre 09:58:54**,
  file_path `2026/SM03473_GeaXw_1.xml`; updated_at 24 settembre 07:11:25;
  is_paid 0, pending_physical_copy, programmed, due_date 30 giugno.
- Buoninfante: unico success **869**, **10 settembre 09:58:54**, collegato a 924 e all'hash reale.
  Nessun success del 7 luglio né del 24 settembre nei risultati; nessun audit pertinente restituito.
- Audit **631** (documento 613, numero 005434275923) è un falso positivo della ricerca LIKE:
  contiene `2351` nell'imponibile 2351,84. Non riguarda la fattura 1/2351 e va escluso dalla timeline.
- FK da import_logs e audit a documents: **ON DELETE SET NULL**, confermate dal DB.
  FK documents verso supplier/legal_entity: NO ACTION. Le anagrafiche non cancellano a cascata le fatture.
  Nessun vincolo UNIQUE diverso dalla PK risulta sulle tre tabelle nell'elenco fornito.

### Conseguenze per le ipotesi

1. I secondi file in deposito/archivio coincidono con le creazioni e i success oggi conservati:
   Marcantuono 25 luglio, Buoninfante 10 settembre. Le registrazioni correnti non sono doppioni fra loro.
2. Non c'è evidenza di un nuovo inserimento Buoninfante il 24 settembre. Il solo updated_at non lo prova;
   la stampa rimane una spiegazione compatibile, non dimostrata, dello stato programmed.
3. L'evento ancora da spiegare è il primo passaggio filesystem: Marcantuono 18 luglio, Buoninfante 7 luglio.
   Non ci sono i relativi success negli import_logs attuali. Senza log/backups non si può affermare
   che in quel primo passaggio esistessero già documenti completi nel DB.
4. Una normale cancellazione della sola fattura lascerebbe l'import_log con FK NULL (e l'audit delete
   se effettuata dal gestionale), non eliminerebbe il log stesso. L'assenza di entrambi rende insufficiente
   tale spiegazione isolata: servirebbero log mai creati, cleanup/restore, altro DB/versione, o ulteriori interventi.
   Non è però prova che non sia avvenuta alcuna cancellazione.
5. Con InnoDB e il codice esaminato, documento + success sono committati insieme. Un rollback normale
   di un tentativo successivo non annulla un commit precedente. Il guasto filesystem non basta a spiegare
   la perdita di un documento già committato e del suo success.
6. **Imported_at NULL di 775 è una discrepanza reale rispetto al percorso d'import esaminato**,
   che lo valorizza anche nella revisione Git di luglio `1baa282`. Non è cancellato dai normali metodi
   di revisione/modifica esaminati. Possibili codice distribuito differente, trigger, modifica SQL o migrazione/restore.
   Non consente ancora di scegliere fra queste ipotesi. Quel NULL esclude 775 dagli "ultimi import" in dashboard,
   ma non dallo scadenziario, che filtra is_paid.
7. La mancanza di UNIQUE consente teoricamente una corsa fra importatori concorrenti; non ci sono però
   due record correnti né due success per questi hash, quindi non è la spiegazione dimostrata di questi casi.

### Prossimo controllo

`fatture_perse_02_storico.sql`: distribuzione degli imported_at mancanti tra documenti con success,
continuità dei log nei giorni dei primi/secondi passaggi, trigger/eventi, conservazione generale degli audit delete.
Chiesta all'utente la cronologia di ripristini, spostamenti server/DB, pulizie o versioni distribuite.
Non correggere imported_at e non rimuovere copie prima di completare questi riscontri.

## 9. Secondo giro MySQL e correzione interpretativa sulla versione

Risultati A/B/C ricevuti dall'utente:

- A: tutti i documenti con success, dai primi del 16 febbraio fino ai 33 del 25 luglio
  (ID 759–791), hanno imported_at NULL; dal 26 agosto (ID 792–832) fino al 24 settembre
  tutti quelli selezionati lo hanno valorizzato. La selezione A richiede un success associato:
  non descrive necessariamente tutti i documenti, inclusi manuali o incompleti.
- B: nell'intervallo 1–26 luglio risultano soltanto 33 success del 25 luglio,
  ID log 746–778, nessuno con document_id NULL. Fra 9 e 11 settembre risulta un solo
  success del 10 settembre, log 869, collegato alla fattura Buoninfante 924.
- C: nessun trigger restituito per le tre tabelle interrogate; la visibilità dipende dai privilegi.

La ricerca Git `-S 'imported_at=datetime.utcnow()'` identifica il cambiamento preciso:
**commit 1baa282 del 7 luglio 2026, ore 12:05:18 +0200**, aggiunge imported_at
all'inserimento ordinario in create_from_fatturapa. Prima era omesso da tale percorso;
il campo esisteva già e il percorso placeholder lo utilizzava.

**Correzione esplicita della lettura precedente:** il NULL di Marcantuono non è un'anomalia
individuale né prova che qualcuno abbia cancellato la data. L'andamento è fortemente compatibile
con una versione precedente a quel cambiamento rimasta distribuita fino all'import del 25 luglio,
aggiornata prima dell'import del 26 agosto. La data del commit non è quella del deploy.
Un intervento massivo sui dati resta logicamente possibile, ma non è necessario per spiegare il NULL.

Le registrazioni di febbraio–giugno e i relativi success sono ancora presenti. Questo rende
insufficiente l'ipotesi di un TRUNCATE totale in luglio senza successiva ricostruzione;
non esclude restore da backup, interventi selettivi o istanze diverse con filesystem condiviso.

Resta non documentato il primo passaggio filesystem del 7/18 luglio. La presenza di copie sia nel
deposito sia nell'archivio è più forte del solo file orfano dopo rollback: nel percorso esaminato
lo spostamento finale avviene dopo i commit o dopo il riconoscimento postparse di un duplicato.
La versione distribuita in quei giorni potrebbe differire e i file potrebbero essere stati copiati
o ripristinati esternamente. Non attribuire quindi automaticamente quelle coppie a commit riusciti
sul database oggi interrogato.

Prossimo controllo limitato: `fatture_perse_03_luglio.sql`, documenti di luglio senza imporre
la presenza di success, più conservazione generale di audit delete e log scollegati.
Da chiarire con il gestore: date dei deploy fra luglio/agosto, eventuali vecchie istanze/URL
o ambienti di prova puntati allo stesso Deposito XML, restore/trasferimenti.
Nessun buco negli ID va presentato come prova di cancellazione: rollback e allocazione AUTO_INCREMENT
possono generarlo anche senza un documento mai committato.

## 10. Terzo giro: F/G/G2 e commit di luglio

F restituisce soltanto nove documenti, ID 750–758, creati il 4 luglio fra 09:33 e 09:48,
con numero, file_name, file_path e import_source NULL, stato verified e nessun import_log.
Sono compatibili con inserimenti manuali, ma la query non ne specifica il document_type.
Non sono riscontri delle fatture XML cercate né dei relativi placeholder (che avrebbero almeno
file_name e nota IMPORT_WARNING nel percorso esaminato).

G: 19 audit delete, tutti scollegati, dal 17 febbraio al **22 maggio 06:15:41**;
940 update fino al 24 settembre, uno scollegato. G2: 984 success dal 16 febbraio al
24 settembre, **17 con document_id NULL**; nessun altro status restituito.
Non equiparare i 19 delete ai 17 success senza confrontarne i documenti: non ogni documento
eliminato deve provenire da import XML. La presenza delle tracce vecchie mostra che lo storico
conserva almeno alcune eliminazioni, ma non prova la completezza dell'audit.

Non emergono audit delete a luglio o settembre, né success scollegati per i due hash (primo giro).
La sola eliminazione dalla UI diventa quindi ancora meno sostenuta dai dati.
Gli ID 750–758 del 4 luglio e l'inizio del batch del 25 luglio a 759 non lasciano un intervallo
evidente per due inserimenti intermedi poi eliminati. Un DELETE ordinario non riavvolge normalmente
l'AUTO_INCREMENT: per quella ricostruzione occorre verificare anche counter reset/restore o un'altra istanza.
Non usare la sequenza ID come prova assoluta: sono possibili assegnazioni esplicite e interventi sul DB.

Lo screenshot Git conferma i commit, non il deploy. Verificati i contenuti:

- `85f767b`, 7 luglio 12:10:29 +0200: find_document_by_file_hash controlla che il documento
  referenziato dal log esista realmente. Non elimina documenti o log; permette di non bloccare
  una reimportazione per un riferimento pendente. È gestione di uno stato preesistente, non causa
  della scomparsa. Con FK sempre attive e SET NULL, il normale delete è già gestito dal DB.
- `2d572d4`, 8 luglio: solo documentazione, nessuna modifica eseguibile. Aggiunge in
  `docs/guides/p7m_troubleshooting.md` una procedura per eliminare documenti di test. Una variante
  conserva i log scollegandoli; l'altra elimina anche le righe import_logs. L'esecuzione manuale
  della seconda variante non produrrebbe l'audit applicativo e non cancellerebbe i file nel deposito.
  **La presenza della guida non dimostra che qualcuno l'abbia eseguita. Nessuna istruzione SQL
  distruttiva della guida è stata eseguita durante questa indagine.**
- `1baa282` valorizza imported_at come già ricostruito. Il percorso precedente eseguiva comunque
  il commit del documento e del success prima dell'archiviazione finale.

Il Dockerfile copia il codice nell'immagine (`COPY . /app`): un commit sul repository, da solo,
non dimostra l'aggiornamento del container in esecuzione. Non è disponibile uno storico dei deploy.

Prossima evidenza utile: conferma di eventuali test con cancellazioni SQL e reset contatori,
restore/dump o installazioni parallele nel periodo; access log/report dell'istanza che scrisse
nel deposito il 7 e il 18 luglio. Altre SELECT sulle stesse righe correnti non ricreano uno storico
eventualmente rimosso. Se non esistono backup/log o memoria operativa, la causa storica può restare
non attribuibile nonostante la verifica dei difetti riproducibili.

## 11. Ricerca delle fonti storiche e ricordo operativo

L'utente non ricorda test specifici e ipotizza soltanto, senza certezza, verifiche sui log
durante le modifiche. Questa risposta NON dimostra cancellazioni SQL, restore o uso della guida.

Letti i log locali app.log/app.log.1/app.log.3 cercando eventi del 7, 18 e 25 luglio e 10 settembre:
nessun evento di queste date. I CSV locali più recenti sono del 22 gennaio.
Ispezionate in sola lettura le directory immediatamente dentro Gestionale Fatture Passive sulla
condivisione: Deposito Copie Fisiche, Deposito DDT, Deposito Pagamenti, Deposito XML;
nessuna cartella log/report/backup a quel livello. Non è una ricerca esaustiva del NAS.

Il compose nel repository monta soltanto /mnt/pastore. I report dell'app sono scritti in
/app/import_debug/import_reports, non in quel mount. Se il deployment effettivo coincide con il
compose, ricreare il container perde i report generati nel suo filesystem non persistente;
un semplice restart non equivale a ricreazione. Configurazioni esterne potrebbero aggiungere mount.
Questo limita le evidenze disponibili, ma NON spiega da solo la perdita di righe sul MySQL esterno.

Prossima richiesta concreta: variabili MySQL log_bin/binlog_expire_logs_seconds/general_log/log_output,
e ricerca dei due nomi nei report/log conservati nel container web operativo o in backup del container.
L'attuale abilitazione del binlog non prova che fosse attivo a luglio o che i file di luglio esistano;
eventuale esame successivo solo in lettura e limitato ai periodi/documenti interessati.
Non attivare ora logging o ripristini: non ricreerebbero gli eventi storici mancanti.

## 12. Binlog disponibili: riscontro operativo

L'utente restituisce log_bin=ON, binlog_expire_logs_seconds=2592000 (30 giorni),
expire_logs_days=0, general_log=OFF e log_output=FILE. Sono impostazioni attuali,
non prova della configurazione storica. SHOW BINARY LOGS elenca binlog.000018–000028;
dimensioni rispettive: 157, 9429, 7461, 322493, 614845, 237543, 1174, 18754,
157, 632, 1030689 byte. La colonna Encrypted è No.

Nomi e dimensioni non stabiliscono le date coperte. Con la retention attuale luglio
potrebbe essere già scaduto; il 10 e 24 settembre potrebbero essere ancora disponibili.
Verificare le date degli eventi prima di concludere. general_log=OFF oggi non esclude
vecchi general log conservati altrove. La retention non garantisce la completezza dello storico.

Passo successivo: ottenere log_bin_basename, datadir, binlog_format, binlog_row_image,
version e verificare accesso alla console del server/container MySQL. Leggere una copia
dei binlog con mysqlbinlog --base64-output=DECODE-ROWS --verbose, senza replay nel DB.
Le date del filtro mysqlbinlog dipendono dal fuso del processo: usare UTC coerentemente
con i riscontri MySQL e filesystem. Cercare INSERT/UPDATE/DELETE pertinenti e operazioni
DDL/restore nel periodo effettivamente coperto; l'assenza di eventi in file incompleti
non dimostra che l'operazione non sia mai avvenuta.

Ulteriore riscontro: MySQL 8.0.44, binlog_format=ROW, binlog_row_image=FULL,
datadir=/var/lib/mysql/, log_bin_basename=/var/lib/mysql/binlog. La configurazione
attuale consente immagini complete delle righe; verificare comunque il contenuto
degli eventi storici. L'utente dispone di Workbench e potenzialmente accesso Debian.
Prima di costruire il comando di estrazione occorre identificare se Debian ospita
il container MySQL: hostname e docker ps (solo nome/immagine/ID, senza inspect/env).

## 13. Primo estratto binlog: importazione 924 confermata

Fonte: testo allegato dall'utente, estratto tramite grep con contesto dal file Debian
`/root/fatture-binlog-lK6ekg.txt`. Non è il binlog decodificato completo.
Il container `db-magazzino-mysql-1` ha ID 0a117854a5fb, coincidente con l'hostname
SQL. L'immagine operativa non include mysqlbinlog; l'estrazione è riuscita tramite
container temporaneo mysql:8.0.44-debian, volumi operativi montati read-only,
entrypoint sh e rete disabilitata. Nessuna modifica del database.

Prima riga temporale restituita: Start 2026-08-12 09:09:18 UTC; ultima: Xid
2026-09-26 08:29:54 UTC. Questi estremi non certificano assenza di lacune intermedie.
Non è disponibile luglio in questo estratto e non si ricostruisce quindi la prima
copia Marcantuono del 18 luglio o Buoninfante del 7 luglio con questi soli dati.

Alla linea originale 124299 compare INSERT documents ID 924 (supplier 55,
legal_entity 3, numero 1/2351, lordo 1959.54). Nella stessa transazione segue
UPDATE con assegnazione file_path da NULL a 2026/SM03473_GeaXw_1.xml.
Seguono righe figlie, INSERT import_logs ID 869 success e INSERT payments ID 901,
document_id 924, importo 1959.54, scadenza 2026-06-30, stato unpaid.
Alle linee 124639–124640 sono presenti Xid=486 e COMMIT.
Timestamp del commit: 2026-09-10 09:58:53.929305 UTC; i DATETIME applicativi
riportano 09:58:54. Non confondere questa differenza subsecondo con due importazioni.

Alla linea 213607 segue un UPDATE documents ID 924. Confrontate tutte le 46
colonne before/after: cambiano soltanto @13 print_status da not_printed a programmed
e @44 updated_at da 2026-09-10 09:58:54 a 2026-09-24 07:11:25.
ID, numero, fornitore, intestazione, importo, file_name, file_path, imported_at,
created_at e is_paid=0 restano invariati. L'header temporale e il COMMIT di questa
seconda transazione non sono inclusi nella finestra grep: il 24 settembre è qui
attestato dal valore updated_at, coerente con il precedente SELECT operativo.

Il codice attuale routes_payments.py:595 chiama mark_documents_as_programmed dopo
la generazione PDF dello scadenziario; document_service.py:361 aggiorna print_status.
Il delta osservato è compatibile con quel percorso e non è una nuova importazione;
non identifica però da solo l'utente o la richiesta HTTP che lo produsse.
Le righe adiacenti mostrano aggiornamenti ad altri documenti, compatibili con batch.

Conclusioni circoscritte: l'importazione del 10 settembre è realmente persistita,
non soltanto copiata su disco. Il suffisso _1 esisteva già in quella transazione.
L'UPDATE mostrato per settembre non è cancellazione/reimportazione. Nel risultato
grep fornito non emergono DELETE o ulteriori INSERT pertinenti, né match Marcantuono.
Non estendere l'assenza di match a prova di continuità assoluta: occorre il testo
completo per verificare confini delle transazioni, DDL/restore e copertura.
Il messaggio di decodifica column type=255 nella finestra contigua riguarda un'altra
tabella/schema (assistente_aziendale.task_lavori), non documents: non prova corruzione
della fattura. Non riprodurre nel rapporto i dati non pertinenti di quella tabella.

Prossimo riscontro: acquisire il file decodificato completo già esistente, senza
ripetere l'estrazione. In parallelo distinguere visibilità nello scadenziario da
persistenza: la scadenza del documento è giugno, non settembre; filtri data e testo
persistenti e intestazione selezionata restano ipotesi da verificare, non colpa
dimostrata dell'operatore.

## 14. Secondo estratto: coda del binlog e limite delle conclusioni

L'utente fornisce il massimo testo recuperabile dal terminale: allegato
a4f1b2ab-189c-47ac-9b51-a159552cd7ff, 116104 byte. Inizia a metà immagine riga;
il primo timestamp esplicito è Xid del 24 settembre 08:14:09 UTC e termina con
End of log file dopo il 26 settembre 08:29:54 UTC. Non contiene documenti 924/775
né i loro nomi/numero cercati; non completa la transazione della 924 alle 07:11.
Nessun DELETE FROM, DROP TABLE o TRUNCATE compare in questo frammento; ciò non
dimostra assenza di cancellazioni nel resto dello storico.

Confronto delle immagini complete documents presenti:
- 1038, Buoninfante 1/2289, intestazione ID 4: cambia print_status in programmed
  e updated_at. Il before contiene già file_path SM03473_GeaZh_1.xml e created_at
  24 settembre 07:47:22. Non è presente l'INSERT corrispondente nel frammento.
- 1031, Buoninfante 1/2205, intestazione ID 3: stesso cambio di stampa;
  before contiene già SM03473_GaBEd_1.xml e created_at 24 settembre 07:37:40.
  Anche qui nessuna prova di una precedente importazione riuscita o cancellazione.
- INSERT effettivi 1039 (1/3207) e 1040 (1/3977), fornitore ID 57, con
  assegnazione file_path e transazioni concluse da COMMIT; successivi aggiornamenti
  di registration_date, doc_status in verified e updated_at.
- Documento 1033: is_paid passa da 0 a 1, con aggiornamento del pagamento e COMMIT.
  Questo illustra una rimozione legittima dallo scadenziario dei non pagati senza
  cancellazione del documento; riguarda un altro documento, non prova la causa
  del caso 924, il cui is_paid è 0 nelle evidenze disponibili.

Il caso 924 non basta a chiudere gli altri casi Buoninfante: nel frammento ci sono
altre fatture con suffisso _1 e creazione il 24 settembre, ma manca il loro storico
precedente. Non attribuire il problema all'operatore e non escludere globalmente
un difetto applicativo. Nessuna ulteriore estrazione richiesta in questa fase,
considerato il limite di materiale dichiarato dall'utente.
