# Import e riconciliazione 2026 — 1 ottobre 2026

## 1) SPEC — Intento e vincoli

Base esaminata: HEAD `7b0cc71`. Correzioni locali, nessuna distribuzione,
importazione operativa, modifica contabile, migrazione o rinomina dello storico.
Il CSV dell'utente è un elenco di anomalie per nome, non una prova di assenza
contabile. Contiene 91 righe: 43 XML/P7M ASSENTE_PER_NOME, 47
SOLO_SENZA_1_DA_VERIFICARE e ZZ_TEST_CONDIVISIONE.txt, escluso.

Fonti: AGENTS.md, docs/00_INDEX.md, architecture.md, database.md,
guides/import_recovery.md, guides/xml_storage_naming.md,
fatturapa/PARSING_REFERENCE.md, precedente indagine del 26 settembre,
codice corrente, test, Git e log locali. I risultati delle indagini precedenti
restano fonti storiche, non verifiche del DB corrente.

## Tracciamento completo prima delle modifiche

- POST /import/run: cartella server -> run_import; upload singolo/multiplo ->
  run_import_files. Entrambi -> _run_import_paths -> import_file per file.
  I batch possono avere esiti diversi; non sono una transazione unica.
- Scansione ricorsiva XML/P7M con estensione senza distinzione di case;
  Archivio/staging/diagnostica esclusi. XML e P7M omonimi entrano entrambi.
- Registro started committato separatamente; staging persistente verificata
  con SHA-256. Non equivale a un documento contabile salvato.
- import_metadata legge identità fiscali originali e hash di ciascun body;
  XML ordinario letto direttamente; P7M estratto con OpenSSL o fallback
  DER/base64. Non è una verifica crittografica della firma.
- Parser v2 xsdata -> fallback legacy; restituisce tutti i body. L'import
  verifica conteggio, tipo/numero/data e importi finiti prima della scrittura.
  I fallback tolleranti non possono superare il precontrollo XML rigoroso.
- Intestatario, fornitore, documenti, righe, IVA, scadenze, DDT e registro
  finale sono nella stessa sessione/transazione. Note di credito: segno
  negativo dei totali, pagamenti/DDT non creati secondo il comportamento esistente.
- Duplicati cercati per numero/data e snapshot storici, poi confrontati per
  identità XML completa e impronta body. Il nome e `_1` non sono identità.
  Nessun UNIQUE nuovo. Documenti storici senza XML verificabile richiedono revisione.
- Flush di tutti i body; copia definitiva verificata; commit unico per file;
  solo dopo commit verifica finale e copia dell'originale nell'Archivio.
  La pubblicazione prima del commit può lasciare una copia orfana: non prova
  salvataggio. L'originale non viene spostato/eliminato nella versione corrente.
- Il registro body con status success è preparato nella transazione, non
  reso persistente prima del commit. Manifest e riepilogo mantengono pending
  fino al commit confermato. Per commit incerto: nuova connessione e lock,
  nessun reinserimento alla cieca. La chiusura Session fa rollback sui guasti.
- Nome leggibile annuale nel deposito; byte identici riusati dopo hash;
  collisione con contenuto diverso -> suffisso SHA-256. Archivio originale
  separato per attempt_id. Successo DB con errore di archivio mostra avviso
  e conserva staging per recupero. CSV/JSONL non sono prova del commit MySQL.
- GET riepilogo/status e polling browser leggono il registro; manage.py
  recover-imports e recupero prima del batch possono scrivere registro e
  filesystem. NON sono strumenti in sola lettura e non sono stati eseguiti
  sull'ambiente operativo in questa indagine.

## Evidenze, storia e limiti

### Codice attuale: difetti riprodotti

1. `_collect_import_files` restituiva set di Path. WindowsPath compara senza
   distinguere case: due voci distinte di un NAS possono collassare prima
   del parser. Test con voci Windows dimostra la perdita; lista conserva entrambe.
   Questo rischio è specifico della piattaforma: NON dimostra che sia avvenuto
   sul deployment Linux o che causi tutte le 43 anomalie.
2. `_duplicate` accettava un documento con XML e quantità dettagli corretti
   anche se total_gross_amount del DB era diverso. Riprodotto con DB isolato:
   import, modifica totale a 999, retry. Ora restituisce conflitto senza inserire.

### Git e log

La versione `b6b4fb0` aveva precheck per nome prima della lettura, controllo
hash comune ai body, commit dentro il ciclo e chiamata di archiviazione dopo
il catch dell'errore DB. Quindi archiviazione e import parziale erano possibili
nel vecchio flusso. `4be5721` introduce il protocollo per file; `574058e`
rafforza recupero/hash; `c0262ff` modifica riuso del deposito e storico.
Questi sono riscontri del codice versionato, non attribuzioni delle anomalie
a un commit o prove della versione distribuita quando ogni file fu elaborato.

Log locali app.log, app.log.1, app.log.3: timestamp tra 5 gennaio e 5 agosto
2026. Nessun file/file_name esatto del CSV nei record JSON disponibili.
Sono presenti vecchi errori NameError e vincoli fornitori di gennaio:
non collegabili ai 90 file senza ulteriore evidenza. Servono registro/log
operativi e versione distribuita per attribuire gli episodi storici.

### Lettura NAS effettuata

Base: `\\192.168.1.111\Aziende_Pastore\Amministrazione\Acquisti\Gestionale Fatture Passive\Deposito XML`.

- Archivio/XML/2026: 771 file; 88 dei 90 nomi XML/P7M del CSV trovati.
  Mancano qui IT01879020517A2026_gs4lQ.xml e IT03830780361_DJYKR.xml.
- Deposito 2026: 980 file; tutti i 90 nomi del CSV trovati. Il conteggio 975
  dell'utente non è riproducibile sullo snapshot corrente; non è una prova
  che il confronto dell'utente fosse sbagliato.
- 85 file leggibili, un body ciascuno; cinque P7M falliscono import_metadata
  con XMLSyntaxError. Posizioni riga/colonna nell'anteprima. Non sono stati
  riparati né importati con recupero XML permissivo.
- 46 delle 47 copie `_1` hanno una controparte dal nome esatto senza `_1`
  con byte identici. Questo prova uguaglianza dei file, NON presenza nel DB.
- SM03473_GaBEd_1.xml non ha controparte esatta SM03473_GaBEd.xml nel deposito.
  Esiste SM03473_GaBED.xml: contenuto diverso, altro destinatario e numero.
  GaBEd_1: TD24, 1/2205, 2026-06-20, destinatario IVA 03185040650.
  GaBED: TD24, 1/2216, 2026-06-20, destinatario IVA 04026780652.
  Cedente IVA 02106670652 per entrambe. Nessuna equivalenza per case.

Cinque P7M da verificare:

- IT04313920656_84YMI.xml.p7m
- IT06655971007SP26u_HV6Z8_1.xml.p7m
- IT06655971007SP26u_HVGQ1_1.xml.p7m
- IT06655971007SP26u_HVIWF_1.xml.p7m
- IT06655971007SP26u_J40IM_1.xml.p7m

**Database operativo non confrontato:** manca una connessione esplicita
raggiungibile in sola lettura o un export. Nessuno dei 90 file è dichiarato
da importare sulla sola assenza del nome. L'anteprima riporta 85 errori
"presenza non verificata" e cinque errori di lettura; non significa 90
import falliti. I dati fiscali degli originali restano negli output locali
ignorati sotto logs/, non in Git. I due report JSON separano archivio/deposito.
Verificata anche la connessione esistente di DevConfig senza esporre credenziali:
connessione non riuscita, OperationalError MySQL 2003; nessuna query sui dati.
partial_file è null quando il database non è disponibile, non una prova di completezza.

## 2) PLAN — Ambito finale

Su richiesta dell'utente è stato rimosso lo strumento separato di riconciliazione,
insieme al relativo servizio e ai test. Gli esiti della lettura già effettuata
restano documentati sopra; i rapporti locali restano sotto logs/.

Restano due file applicativi modificati e due file di test:

- D:\Progetto_Database_Acquisti\app\services\import_service.py
- D:\Progetto_Database_Acquisti\app\services\import_recovery_service.py
- D:\Progetto_Database_Acquisti\tests\test_import_lifecycle.py
- D:\Progetto_Database_Acquisti\tests\test_import_storage_naming.py

Nessuna modifica a schema, configurazione, dati operativi o protocollo transazionale.

## 3) IMPLEMENT — Correzioni conservate

La scansione usa una lista per conservare nomi distinti solo per case su Windows.
Il controllo duplicati verifica i tre totali DB rispetto al DTO, rispettando il
segno delle note di credito. Totali discordanti producono un conflitto visibile.
Il commit unico per file e il recupero dei commit incerti restano invariati.

## 4) VERIFY — Validazione e limiti

Prima della rimozione: 36 test superati, 26 MySQL saltati; ulteriori esecuzioni
mirate: 25 test lifecycle e quattro test dell'anteprima superati.
I test dell'anteprima sono stati rimossi insieme allo strumento.

Comando per la suite import rimasta:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_import*.py'
git diff --check
```

Copertura conservata: XML multi-body, retry, errore secondo salvataggio con
rollback senza archivio, commit fallito/ACK perso, crash e recupero, nomi
case-distinct, suffisso `_1` con contenuto uguale/diverso e totali DB discordanti.

Non verificati sul server: MySQL operativo, versione distribuita, concorrenza
reale e durabilità NAS. Il codice locale non equivale a una distribuzione.
