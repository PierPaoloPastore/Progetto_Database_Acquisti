# Export CBI / SEPA XML

Questa guida descrive la prima implementazione del generatore XML per bonifici fornitori dallo scadenziario.

## Stato attuale

- Il generatore produce un XML ISO 20022 `pain.001.001.03` con profilo interno `generic_pain001`.
- Il file viene scaricato dallo scadenziario e non modifica lo stato dei documenti.
- La generazione non registra pagamenti, non marca documenti come pagati e non scrive righe di audit nel database.
- Il profilo generico e' una base SEPA: ogni banca puo' richiedere varianti proprie.

## Uso operativo

1. Avviare l'applicazione con `python manage.py runserver`.
2. Aprire lo scadenziario: `http://127.0.0.1:5000/payments/schedule`.
3. Selezionare uno o piu' documenti da pagare.
4. Scegliere il conto ordinante dal menu "Conto ordinante".
5. Cliccare "Genera CBI".
6. Caricare il file XML scaricato nel portale della banca per la validazione.

## Validazioni applicate

La generazione si blocca con un messaggio leggibile se:

- non sono selezionati documenti;
- manca il conto ordinante;
- l'IBAN ordinante non e' valido;
- un fornitore non ha IBAN valido;
- i documenti appartengono a intestazioni diverse;
- il conto ordinante non appartiene all'intestazione dei documenti;
- un documento non ha residuo da pagare.

## Dati usati dal gestionale

- Ordinante: `BankAccount.iban` e intestazione collegata.
- Beneficiario: `Supplier.name` e `Supplier.iban`.
- Documento: `Document.document_number`, `Document.document_date`, `Document.total_gross_amount`.
- Residuo: campo runtime `remaining_amount` calcolato da `payment_service.attach_payment_amounts()`.

## Struttura tecnica

- Servizio: `app/services/cbi_export_service.py`.
- Profilo attuale: `generic_pain001`.
- Route download: `POST /payments/schedule/cbi`.
- UI: `app/templates/payments/schedule.html`.
- JS download/anti-doppio-click: `app/static/js/schedule.js`.

Il servizio e' progettato a profili: per una banca specifica aggiungere un nuovo `CbiProfile` in `CBI_PROFILES` e regolare namespace, versione e regole richieste.

## Quando una banca rifiuta il file

Richiedere alla banca il manuale tecnico del tracciato, cercando in particolare:

- versione `pain.001` richiesta;
- profilo CBI o SEPA specifico;
- obbligo o meno del BIC;
- eventuale codice azienda CUC/SIA;
- lunghezze massime e caratteri ammessi;
- regole sulla causale;
- nome file richiesto.

Poi creare un profilo banca dedicato invece di modificare il profilo generico.
