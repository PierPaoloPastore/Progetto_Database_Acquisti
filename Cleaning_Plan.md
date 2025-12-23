# Cleaning Plan

## Goals
- Keep the codebase lean without changing behavior.
- Reduce legacy paths once xsdata coverage is stable.
- Maintain docs and lessons as source-of-truth.

## Candidate Areas
- Parsers: consolidate shared cleaning steps; monitor legacy fallback usage.
- Services: remove unused helpers and imports.
- Templates/static: prune unused files after reference scan.
- Scripts: delete one-off tools only after confirming no use.

## Guardrails
- No DB schema changes.
- No behavior changes without manual verification.
- Always confirm references before deleting files.

## Steps
1. Inventory unused files and dead code.
2. Classify risk (low/medium/high).
3. Apply low-risk cleanup first.
4. Add tests for parsing edge cases before deeper refactors.
5. Re-validate imports, review views, and payments.

## Validation Checklist
- Import a subset of P7M files with known quirks.
- Open document list/review/payment views.
- Check logs for new parsing errors.
