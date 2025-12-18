Last updated: 2025-12-17

# Pagamenti — UI/UX aggiornamenti

Modifiche introdotte nella vista Pagamenti (tab “Nuovo Pagamento”) per gestire meglio spazi e leggibilità.

## Cosa è cambiato
- Lista fatture verticale: l’elenco usa `invoice-body` con `overflow-y: auto` e `max-height: 70vh` per scroll verticale, niente scroll orizzontale.
- Colonne compattate: griglia ridotta (gap e larghezze minori) per far convivere form e PDF viewer, con `min-width: 0` per l’1fr e `white-space: nowrap` + ellissi.
- Importo dovuto affiancato: nuova colonna “Dovuto” mostra il residuo da saldare accanto al campo “Importo pagato”.
- Viewer PDF più stretto: `split-container` ora usa `grid-template-columns: 1.6fr 1fr` (form più ampio, viewer ~25% più stretto).

## File toccati
- `app/templates/payments/inbox.html`: struttura lista e colonna “Dovuto”.
- `app/static/css/payments.css`: griglia lista, overflow verticale, ellissi, proporzioni split view, riduzione font/padding nel form.
- `app/static/js/payments.js`: filtro combinato testo+data (già presente; nessun cambiamento per questi punti).

## Note di manutenzione CSS
- La lista poggia su due wrapper (`invoice-list` > `invoice-body`): eventuali altezze vanno regolate su entrambi se si cambia il layout.
- Evitare di rimuovere `min-width: 0`, `white-space: nowrap`, `text-overflow: ellipsis` sulle colonne o il testo tornerà a capo in verticale.
- Se il viewer PDF deve cambiare dimensione, regolare `grid-template-columns` in `.split-container`; per mobile resta 1 colonna via media query esistente.
- Se servono più colonne o campi aggiuntivi, preferire la riduzione dei gap e l’uso di `minmax()` prima di aumentare il break verso l’overflow orizzontale.

## Come verificare rapidamente
- UI: aprire `http://localhost:5000/payments/`, tab “Nuovo Pagamento”. Ridimensionare la finestra per controllare che la lista scrolli solo in verticale e che testo/valori restino su una riga con ellissi.
- PDF viewer: confermare che l’iframe a destra occupi ~40% della larghezza in desktop e scenda sotto la lista in mobile.
