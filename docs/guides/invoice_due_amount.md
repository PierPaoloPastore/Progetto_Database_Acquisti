# Importo fattura dagli importi di pagamento XML

Aggiornamento: 2 ottobre 2026.

Per tutti i fornitori, il campo esistente `total_gross_amount` viene valorizzato
con la somma degli `ImportoPagamento` presenti nel corpo XML della fattura.
Se nessun importo è presente, usa `ImportoTotaleDocumento`; rimangono i fallback
preesistenti del parser se anche il totale documento manca. Zero esplicito vale
zero. Si sommano tutte le rate e tutti i blocchi di pagamento del singolo corpo.
La scelta è condivisa dai due parser tramite `InvoiceDTO.__post_init__`.
Importi presenti ma invalidi o non finiti bloccano l'importazione.

Non vengono conservati due totali: anche le viste e i report che usano
`total_gross_amount` mostrano ora l'importo così scelto. Imponibile e IVA restano
quelli XML. Non è prevista alcuna nuova colonna o migrazione dello schema.
Le note di credito TD04 mantengono il totale documento con segno negativo e
la gestione preesistente di allocazioni e disponibilità.

Il calcolo condiviso dei pagamenti usa il totale salvato, senza ricostruirlo
dalle scadenze modificabili. Residuo e saldo considerano pagamenti effettivi e
compensazioni. La dashboard somma i residui; gli export usano gli stessi residui.
Un importo zero è già marcato saldato all'importazione.

## Fatture esistenti

Non vengono aggiornate automaticamente e reimportare un duplicato non corregge
il totale. Se il totale salvato differisce dal nuovo criterio, il controllo dei
duplicati segnala un conflitto da verificare.

Per recuperarle, proporre prima un rapporto dagli XML originali verificabili:
ID, file/hash, identità di fornitore e destinatario, numero/data/tipo, corpo XML,
totale attuale, importi di pagamento e nuovo totale proposto. File mancanti,
alterati, ambigui o discordanti non producono aggiornamenti presuntivi.
Dopo revisione, aggiornare soltanto le corrispondenze certe in transazione e
ricalcolare `is_paid` con il servizio condiviso, registrando evidenza e audit.
Non dedurre importi dalle scadenze o dal fornitore.

## Verifica

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_original_due_amount.py -v
```

Test su factory Flask, SQLite temporaneo e XML sintetici: totale XML 122 con
pagamento 100, importo assente, zero, più rate 40+60, parziale 30 con residuo 70
e saldo con ulteriori 70. Verificano entrambi i parser, persistenza, scadenze
modificate, dashboard, export CBI, importi invalidi e note di credito.
In staging MySQL ripetere importazione, pagamento parziale e saldo, verificando
residuo, `is_paid`, dashboard e `InstdAmt` CBI. Nessuna migrazione da applicare.
