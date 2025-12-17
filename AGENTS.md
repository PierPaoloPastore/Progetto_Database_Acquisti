# Repository Guidelines

This guide helps contributors work on the Gestionale Acquisti Flask monolith safely and consistently.

## Project Structure & Module Organization
- `app/`: factory in `app/__init__.py`; `models/` for SQLAlchemy entities; `repositories/` for DB access; `services/` for business logic; `parsers/` for FatturaPA ingestion; `web/` for HTML routes/templates; `api/` for JSON blueprints; assets in `static/` and `templates/`.
- `docs/`: entrypoint `docs/00_INDEX.md` with architecture, DB notes, and agent context.
- `data/` holds import samples; `logs/` collects runtime logs; `plans/` and `_archive/` store meta and historical material.

## Build, Test, and Development Commands
- Install deps (use a virtualenv): `pip install -r requirements.txt`.
- Prepare DB: update `DevConfig` in `config.py` with local MySQL credentials, then `python manage.py create-db`.
- Run dev server: `python manage.py runserver` (honors `FLASK_RUN_HOST` and `FLASK_RUN_PORT`).
- Quick start equivalent: `python run_app.py`.

## Coding Style & Naming Conventions
- Python 3.12; follow PEP8 with 4-space indent. Use `snake_case` for functions/vars, `PascalCase` for classes, and concise Italian comments where needed.
- Keep layers clean: parsing in `parsers`, persistence in `repositories`, orchestration in `services`, presentation in `web`/`api`. Avoid side effects inside models.
- Prefer explicit imports and type hints; use the JSON logging set up in `app/extensions.py` instead of ad-hoc prints.

## Testing Guidelines
- No formal suite yet; add `pytest` tests under `tests/` using `test_*.py` naming. Example run: `pytest -q`.
- Use the Flask app factory for integration tests; isolate DB-dependent tests with a temporary schema or fixtures instead of touching production data.
- When adding parsers or services, cover happy path plus validation errors and edge cases (missing tags, inconsistent totals).

## Commit & Pull Request Guidelines
- Follow Conventional Commits as seen in history (e.g., `fix(payments): resolve batch payment registration bug`).
- PRs should include: short summary, linked issue/plan, clear steps to test, and screenshots for UI-facing changes. Flag any DB-impacting change explicitly.
- Do not modify `config.py`, DB schemas, or logging defaults unless explicitly requested.

## Security & Configuration Tips
- Never commit secrets or real invoices; rely on `.env`/local env vars for credentials and use sample data under `data/` for tests.
- Keep `logs/` and other generated artifacts out of version control; respect `.gitignore`.

## Mandatory Compound Workflow

For any task that is not a trivial change, you MUST follow this compound loop and present the sections explicitly in this order:

### 1) SPEC — Intent & Constraints
- Restate the goal clearly.
- List constraints derived from this repo (layers, DB safety, logging, naming).
- State which documentation files will be consulted (start from `docs/00_INDEX.md`).

### 2) PLAN — Step-by-step approach
- Provide a concise, ordered plan.
- List all files that will be modified (full paths).
- Highlight risks (DB schema, data migration, regressions) and mitigations.

### 3) IMPLEMENT — Code changes
- Apply the plan with minimal, coherent changes.
- Do not duplicate logic; refactor or reuse existing code.
- Keep business logic in `services/`, persistence in `repositories/`.

### 4) VERIFY — Validation
- Describe how to verify the change (commands, manual steps, SQL checks).
- If automated tests are missing, provide a manual verification checklist.

### Definition of trivial change
A change is considered trivial only if:
- it affects a single file,
- does not change cross-layer behavior,
- does not touch DB schema or business rules,
- and is ≤ ~20 lines.

Trivial changes may skip SPEC and PLAN but MUST include VERIFY.

### Safety stop
If the task requires:
- DB schema changes,
- data migrations,
- wide refactors across layers,

STOP after SPEC + PLAN and ask for confirmation before implementing.
