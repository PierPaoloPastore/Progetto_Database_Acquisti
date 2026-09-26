Last updated: 2026-09-26

# Deposito XML, archivio e nomi dei file

## Ambito

La convenzione introdotta il 2026-09-26 si applica alle copie dei nuovi import
XML/P7M, dopo l'aggiornamento dell'applicazione sul server. Non rinomina i file
gia importati e non richiede migrazioni o modifiche allo schema del database.

## Flusso di salvataggio

Nel normale import completato correttamente, il gestionale:

1. Legge il file e ricava i dati delle fatture.
2. Copia il file nel **Deposito XML**, sotto la cartella dell'anno, con il nuovo
   nome leggibile. Il contenuto del file non viene modificato.
3. Salva nel database i dati e il percorso relativo della copia in
   `documents.file_path`, usato per accedere al file dal gestionale.
4. Sposta l'originale in `Archivio/XML/ANNO`, conservandone il nome salvo
   l'aggiunta di un suffisso numerico se quel nome esiste gia.

Il deposito corrisponde al percorso configurato in Impostazioni, campo
**Deposito XML** (`XML_STORAGE_PATH`; fallback `storage/xml`). Sul server Debian
puo essere una directory locale oppure una cartella di rete montata.

La posizione dell'archivio dipende dalla modalita di importazione:

| Modalita | Posizione dell'archivio |
| --- | --- |
| Caricamento dal browser | Dentro il Deposito XML |
| Import da cartella server | Dentro la cartella di provenienza selezionata |

Se la provenienza coincide con il deposito, una fattura produce ad esempio:

```text
Deposito XML/
├── 2026/
│   └── 2026-09-26_Fornitore_prova_FT-123.xml
└── Archivio/
    └── XML/
        └── 2026/
            └── IT01234567890_ABC.xml
```

Le due copie hanno lo stesso contenuto e ruoli diversi: copia collegata al
gestionale e originale elaborato. Non costituiscono un backup indipendente
se risiedono sullo stesso disco.

## Convenzione del nome nel deposito

Formato: `AAAA-MM-GG_Fornitore_Numero.xml`.

Esempio: data `2026-09-26`, fornitore `Fornitore prova`, numero `FT/123`
producono `2026-09-26_Fornitore_prova_FT-123.xml`.

- La data e quella della fattura; in sua assenza si usa la data di registrazione,
  oppure `senza-data` se mancano entrambe.
- Il nome del fornitore viene normalizzato per l'uso nel filesystem e limitato
  a 80 caratteri. Se assente o vuoto dopo la normalizzazione, si usa `fornitore`.
- Nel numero fattura `/` diventa `-`; il numero viene poi normalizzato e limitato
  a 60 caratteri. Se manca o risulta vuoto, si usa `senza-numero`.
- La normalizzazione usa `werkzeug.utils.secure_filename`: spazi e caratteri
  non adatti al filesystem vengono convertiti o rimossi.
- Le estensioni `.xml`, `.p7m` e `.xml.p7m` vengono mantenute, in minuscolo.
  Il naming non estrae ne altera il contenuto dei file firmati.
- In caso di nome gia presente, si aggiunge `_1`, `_2`, ecc. prima
  dell'estensione, senza sovrascrivere il file precedente.
- Un XML con piu fatture resta un solo file: il nome usa i dati della prima
  fattura e aggiunge `_multi` prima dell'estensione. I documenti creati
  condividono il percorso di quel file.
- Gli import con parsing incompleto mantengono il nome sorgente, con eventuale
  suffisso per evitare collisioni.

La cartella annuale segue la logica esistente: prima data fattura o data di
registrazione disponibile scorrendo le fatture, altrimenti anno corrente.
Per gli import con parsing incompleto si usa l'anno di modifica del file,
con ripiego sull'anno corrente.

## Compatibilita e duplicati

`documents.file_name` conserva il nome sorgente (con `#bodyN` per distinguere
le fatture di un XML multiplo); `documents.file_path` contiene il nuovo percorso.
Anche i download continuano a proporre il nome sorgente. Vecchi e nuovi nomi
possono quindi convivere nel deposito senza rinominare lo storico.

I controlli dei duplicati restano quelli esistenti: nome sorgente, hash del
contenuto e identita contabile della fattura. Il suffisso numerico nel filesystem
evita collisioni di nomi, ma non sostituisce questi controlli.

La scansione da cartella server esclude i percorsi che contengono una componente
chiamata `Archivio`, anche se quella cartella viene selezionata direttamente.
Ricaricare i file dal browser li sottopone invece all'import normale: quelli
riconosciuti vengono saltati, quelli non riconosciuti possono essere importati.
Non e quindi una verifica in sola lettura della completezza dell'archivio.

## Verifica

Test automatici senza database reale, dalla radice del progetto:

```sh
python -m unittest discover -s tests -p 'test_import*.py' -v
```

I test coprono nomi leggibili, contenuto preservato, estensioni, collisioni,
campi mancanti, nomi lunghi, XML multipli, collegamento al documento,
archiviazione dell'originale e riconoscimento della reimportazione.

Verifica manuale in ambiente di prova dopo l'aggiornamento dell'applicazione:

1. Importare un XML di prova non ancora presente.
2. Controllare il nuovo nome nella cartella annuale del deposito e l'originale
   nell'archivio previsto dalla modalita di importazione.
3. Aprire/scaricare il file dal documento e verificare che il contenuto sia corretto.
4. Ricaricare lo stesso XML e controllare che il resoconto lo indichi come duplicato.
5. Aprire un documento precedente all'aggiornamento e verificare che il suo file
   sia ancora accessibile.

Riferimenti: `app/services/import_service.py`, `app/services/settings_service.py`
e `tests/test_import_storage_naming.py`.
