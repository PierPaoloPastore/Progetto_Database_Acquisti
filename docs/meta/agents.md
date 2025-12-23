# AGENTS GUIDELINES FOR THIS REPO

## Overview
Questo progetto è una webapp Flask monolitica per la gestione delle fatture di acquisto, con:
- models (SQLAlchemy)
- repositories (data access)
- services (business logic)
- web (views + templates)
- api (endpoint JSON)
- parsers per FatturaPA (xsdata primary + legacy fallback, P7M cleaning)
- MySQL come database

## Coding Style
- Linguaggio: Python 3.12.
- Stile dei commenti: italiano chiaro.
- Naming: snake_case per funzioni/variabili.
- Classi: PascalCase.
- Evitare side effects nei modelli.

## Coding Guidelines
- Prima di istanziare un Modello o filtrare, leggi la definizione della classe SQLAlchemy per confermare i nomi dei campi. Non assumere che i parametri della funzione chiamante corrispondano 1:1 alle colonne del DB.

## Refactoring Guidelines
- Quando modifichi una vista, controlla `routes_*.py` per vedere quale file HTML viene chiamato.
- Se rinomini un template, usa `grep` per assicurarti che tutti i `render_template` siano aggiornati.

## Logging
- Usare sempre logging JSON dell'app (extensions.py).
- Non cambiare la configurazione DB.

## Non fare mai:
- modificare config.py senza esplicita richiesta
- cambiare nomi tabelle o colonne
- riscrivere importatori senza conferma
- cambiare schema/migrazioni del DB senza richiesta esplicita
- committare `__pycache__/`, `*.pyc`, `logs/*.log`

## Testing / Verifica
- Usa le istruzioni di esecuzione in README.md (TODO se mancanti).
- Controlla che non ci siano eccezioni nei log.

## Pull Request Style
Ogni modifica proposta dal modello deve includere:
- Summary
- Files changed
- Reasoning
- Steps to test

