# Code Cleanup Plan

## Goals
- Remove obsolete or duplicated code while keeping behavior stable.
- Reduce parsing tech debt (xsdata primary, legacy fallback only when needed).
- Improve test coverage for import/parsing edge cases.

## Scope (candidate areas)
1. Parsers
   - Confirm which helpers in `app/parsers/fatturapa_parser.py` are still used by fallback.
   - Consolidate common cleaning steps; avoid double-cleaning.
   - Track fallback usage and define deprecation criteria.
2. Import flow
   - Review `import_service` for duplicated logging or dead paths.
   - Ensure error classification (skip vs error) is consistent.
3. Docs and lessons
   - Consolidate duplicated lessons files or add a single source of truth reference.
   - Remove stale references to old parser architecture.
4. Scripts and utilities
   - Audit `scripts/` for unused tools or one-off helpers.
5. Web/templates
   - Identify unused templates and static assets.
   - Remove legacy route/template references after confirmation.

## Non-goals
- No DB schema changes.
- No behavior changes without tests or explicit approval.

## Steps
1. Inventory
   - Search for TODO/FIXME and unused imports.
   - Build a list of unused modules, scripts, and templates.
2. Risk classification
   - Low risk: unused files, dead code, unused imports.
   - Medium risk: refactors within parsing or import_service.
   - High risk: changes that alter parsing outcomes or DB writes.
3. Execution
   - Apply low-risk cleanup first.
   - Add tests for parsing edge cases before medium/high risk changes.
   - Keep legacy fallback until xsdata coverage is verified.
4. Validation
   - Re-run P7M import on a known problematic subset.
   - Check `import_logs` for new error patterns.
   - Smoke-test document review and payments views.

## Risks and mitigations
- Risk: Removing fallback breaks corrupted P7M imports.
  - Mitigation: Keep fallback until regression tests pass.
- Risk: Removing templates breaks routes silently.
  - Mitigation: Confirm `routes_*.py` references before deletion.

## Outputs
- Cleanup checklist with files to delete/change.
- Test notes for parsing/import verification.
