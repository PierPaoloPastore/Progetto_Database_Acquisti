# Indagine: fattura 924 non visibile nello scadenziario

Data: 24 settembre 2026. Codice esaminato: commit `86b5197` e cronologia dal 10 settembre.

## Esito e limiti

Non ci sono prove sufficienti per attribuire una cancellazione al programma o una svista all'operatore.
La riga fornita dall'utente e il codice sono più compatibili con una fattura già esistente dal 10 settembre,
aggiornata il 24 settembre, che con una fattura creata nuovamente il 24 settembre.
Questa conclusione presuppone che i timestamp nella riga corrispondano a imported_at, created_at e updated_at:
le query allegate verificano i nomi delle colonne senza dipendere dal loro ordine nel dump.

Il database configurato (`db-magazzino-mysql-1`, schema `gestionale_acquisti`) non è raggiungibile
da questa sessione: risoluzione del nome host fallita. Non sono state eseguite query sui dati reali.
I report CSV locali arrivano a gennaio e i log locali disponibili ad agosto; non documentano il periodo
10–24 settembre. Gli ID 924 trovati nei report di gennaio appartengono ad altri file e non costituiscono
evidenza sulla fattura in esame. La versione realmente distribuita sul server va verificata.

## Elementi specifici della fattura

- ID 924; numero 1/2351; data documento 30 giugno 2026; totale 1.959,54 euro.
- supplier_id 55 e legal_entity_id 3 sono due anagrafiche differenti. Nei vecchi log locali
  ALFREDO BUONINFANTE & C. SPA compare come fornitore, non come intestatario interno.
  I nomi associati ai due ID nel database reale devono essere confermati.
- imported_at e created_at apparentemente 10 settembre 2026, 09:58:54; updated_at 24 settembre, 07:11:25.
- print_status `programmed`; doc_status `pending_physical_copy`; physical_copy_status `missing`; is_paid 0.
- Il suffisso `_1` nel percorso archiviato indica una collisione di nomi sul filesystem quando fu salvato
  il file. Non dimostra né una seconda fattura nel DB né la data di una reimportazione.

## Percorsi verificati

### Scadenziario e ricerca

`app/web/routes_payments.py`, funzione `schedule_view`, seleziona tutti i documenti con `is_paid = false`.
Non esclude copie fisiche mancanti, fatture da verificare, documenti programmati o documenti senza
righe in payments. Non applica il limite di 300 documenti dell'elenco documenti.
`_build_schedule_rows` mantiene tutte le righe ricevute, comprese quelle senza scadenza.
I gruppi sono per intestatario interno (`legal_entity_id`), non per fornitore.

`app/static/js/schedule.js` applica poi filtri nel browser e li conserva in localStorage,
chiave `schedule_filters_v1`. Riaprendo la pagina senza parametri vengono ripristinati.
Date e stato riguardano la scadenza, non la data di importazione. Un intervallo di settembre
o lo stato "In scadenza" esclude una fattura con scadenza in giugno.
Anche soglie di importo e testo residuo escludono righe. Il residuo può cambiare dopo pagamenti o compensazioni.

Il testo è confrontato per sottostringa, ignorando solo maiuscole/minuscole. `12351` non trova `1/2351`;
spazi iniziali o doppi possono impedire la corrispondenza. Lo spazio finale dopo il nome del fornitore
riportato dall'utente, da solo, non è una spiegazione: nel testo della riga il nome è seguito da uno spazio
e dall'intestatario. Verificato su un testo conforme al template.

Il pulsante "Totale da pagare" punta alla pagina senza query: in presenza di filtri salvati li ricarica.
Per escludere i filtri usare il vero pulsante di azzeramento oppure `/payments/schedule?status=all`.

### Aggiornamento del 24 settembre

`schedule_print` in `app/web/routes_payments.py` chiama `mark_documents_as_programmed` dopo la generazione
del PDF. La funzione in `app/services/document_service.py` aggiorna print_status e fa commit.
L'onupdate SQLAlchemy del modello aggiorna anche updated_at, lasciando created_at e imported_at invariati.
Questo comportamento è stato riprodotto su SQLite in memoria con il modello reale.

È dunque plausibile che l'orario del 24 settembre corrisponda a una stampa/programmazione.
Non è dimostrato che sia successo: anche altre modifiche aggiornano il timestamp.
Questa operazione non registra un audit specifico della stampa e l'audit documenti non identifica
l'operatore; l'assenza di audit non equivale ad assenza di modifiche.

### Importazione e duplicati

Il percorso ordinario confronta nome file, hash e identità contabile (tipo, fornitore, numero normalizzato,
data). Quando trova la fattura restituisce il documento esistente e non lo ricrea né gli riscrive i timestamp
di importazione. La rinomina del file, da sola, non dovrebbe superare tutti questi controlli.
Un nuovo inserimento attraverso questo percorso riceve timestamp correnti.

Sono necessari il dettaglio del report del 24 settembre e gli import_logs per stabilire se proprio
questa fattura risultasse `success`, oppure se il batch avesse importato altri file e saltato questa.
I controlli preliminari dei duplicati non scrivono sempre un import_log persistente: il CSV è importante.
Prima della correzione del 23 settembre, il ramo postcheck tentava di registrare `skipped` nel DB,
incompatibile con il vincolo documentato. Ciò poteva produrre insieme "saltata" e "errore", ma non
cancellava una fattura già registrata con una precedente transazione completata.

### Altri casi da distinguere

| Caso | Effetto possibile | Compatibilità con la 924 / verifica |
| --- | --- | --- |
| is_paid erroneamente true o NULL | Esclusione già nella query server | Il valore fornito è oggi 0; lo storico non è noto. Controllare payments, compensazioni e audit. |
| Scadenza stimata o modificata | Spostamento fra filtri temporali | Il fallback può usare fine mese della data fattura. Confrontare XML, documents.due_date e payments.due_date. |
| Intestatario/fornitore differente | Altro gruppo o ricerca che non corrisponde | Confrontare anagrafiche 55 e 3, XML e audit. Possibili anagrafiche duplicate con identificativi fiscali differenti. |
| Cancellazione esplicita | Vera rimozione e successiva importabilità | Esiste nelle route documenti; salva uno snapshot audit, con document_id eventualmente NULL dopo eliminazione. Cercare anche nel payload. |
| Inizializzazione DB / ripristino backup / altro server | Perdita o divergenza di dati | Esiste una funzione esplicita di inizializzazione, non un timer di 14 giorni. Verificare log di amministrazione, backup e host/schema. |
| Import del 10 settembre non completato | File caricato ma documento non salvato | Cercare success/error del file, non il solo totale del batch. Il record fornito con creazione il 10 contrasta con questa ipotesi per la 924. |
| XML mancante o non visualizzabile | Anteprima fallita | Non elimina il record né lo esclude dallo scadenziario. |
| Pagina già aperta prima dell'import | Elenco non aggiornato fino al ricaricamento | Lo scadenziario non si aggiorna automaticamente dopo importazioni svolte altrove. |
| Filtri elenco documenti / limite 300 | Assenza nell'elenco generale | È un percorso diverso dallo scadenziario; non spiega direttamente la segnalazione confermata. |

## Criticità aggiuntive nel codice, non dimostrate come causa dell'episodio

- XML con più body: i DTO condividono l'hash del file; dopo il commit del primo body,
  il controllo per hash può trovare quel primo documento e scartare i successivi. Una reimportazione
  può inoltre fermarsi già sul nome base. Serve verificare se il file interessato ha più body.
- Il controllo contabile primario non include l'intestatario e normalizza i separatori del numero:
  può accorpare documenti che richiederebbero distinzione. Non cancella record già presenti.
- Il confronto LIKE sui nomi multi-body non effettua escape di `_` e `%`: possibile falso duplicato
  per alcuni nomi. Non implica cancellazione.
- Il file viene copiato prima del completamento della transazione: un errore può lasciare una copia
  orfana e generare il suffisso `_1` al tentativo successivo. La presenza del file non prova il commit.
- L'hash viene segnato come già incontrato nel batch prima del successo: una seconda copia nello stesso
  batch può essere saltata anche se il primo tentativo fallisce.
- Il blocco import è locale al processo: import concorrenti da processi differenti richiedono una verifica
  dei vincoli effettivi del DB. Questo riguarda eventuali doppioni, non la sparizione dopo due settimane.
- La selezione dei file preferisce XML a P7M omonimo ed esclude metadati: il numero dei file scelti non
  coincide necessariamente con il numero delle fatture persistite.

## VERIFY — Riscontri ottenuti e prossima verifica decisiva

Eseguiti senza DB reale: aggiornamento ORM `programmed` su SQLite in memoria; costruzione delle righe
scadenziario con stati della fattura fornita; esecuzione della parte reale dei filtri JavaScript con Node
su dati fittizi (nessun filtro, intervallo settembre, in scadenza, numero con/senza slash, spazi).
La logica dei filtri non presenta differenze Git tra il commit del 7 settembre e quello attuale.

Le query in `indagine_fattura_924_2026-09-24.sql` sono tutte SELECT. Eseguirle sul database realmente
utilizzato dagli operatori. Incrociare i risultati con report CSV e access log del 10 e 24 settembre,
backup precedenti all'episodio, versione distribuita e filtri del browser dell'operatore.
I timestamp richiedono attenzione al fuso del server e alla convenzione UTC utilizzata dall'app.

Conclusione provvisoria: nessuna evidenza di una cancellazione automatica dopo 14 giorni; ipotesi prioritaria
visibilità/ricerca, con aggiornamento del record dovuto a un'operazione successiva. Attribuzione definitiva
sospesa fino al controllo dello storico reale. Nessuna modifica al codice applicativo o ai dati.
