# AGENTS GUIDELINES FOR THIS REPO

## Overview
Questo progetto è una webapp Flask monolitica per la gestione delle fatture di acquisto, con:
- models (SQLAlchemy)
- repositories (data access)
- services (business logic)
- web (views + templates)
- api (endpoint JSON)
- parsers per FatturaPA
- MySQL come database

## Coding Style
- Linguaggio: Python 3.12.
- Stile dei commenti: italiano chiaro.
- Naming: snake_case per funzioni/variabili.
- Classi: PascalCase.
- Evitare side effects nei modelli.

## Logging
- Usare sempre logging JSON dell'app (extensions.py).
- Non cambiare la configurazione DB.

## Non fare mai:
- modificare config.py senza esplicita richiesta
- cambiare nomi tabelle o colonne
- riscrivere importatori senza conferma

## Testing / Verifica
- Comando per verificare che tutto funzioni:
  - `python manage.py runserver` deve avviarsi senza errori
  - nessuna eccezione nei log

## Pull Request Style
Ogni modifica proposta dal modello deve includere:
- Summary
- Files changed
- Reasoning
- Steps to test

