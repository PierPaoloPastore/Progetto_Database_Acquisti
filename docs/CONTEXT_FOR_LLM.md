# LLM context pack
Last updated: 2025-12-15

1) Project overview
- Monolithic Flask app (Python 3.12) that manages the full lifecycle of purchase documents, centered on a unified `documents` supertype with shared workflows for import, review, physical copies, deadlines, and payments. Source of truth: [README](../README.md).

2) What is implemented today
- FatturaPA XML/P7M import with DTOs, xsdata primary + legacy fallback, tag-name sanitization, encoding fallbacks, delivery note expectations, and TD04 credit notes as `document_type='credit_note'`. Source: [README](../README.md), [P7M troubleshooting](guides/p7m_troubleshooting.md).
- Document review with statuses (`imported`, `verified`, `rejected`, `cancelled`, `archived`) and physical copy tracking. Source: [README](../README.md).
- Delivery notes (`delivery_notes`) for deferred invoices and PDF inbox with matching states. Source: [architecture](architecture.md).
- Payment scheduling via `payments`, payment PDFs in `payment_documents`, and M:N reconciliation through `payment_document_links`. Source: [README](../README.md), [architecture](architecture.md).
- Supplier/legal entity registry, categories on invoice lines, notes, exports/reports (IVA, supplier statements, CSV). Source: [README](../README.md).

3) Architecture (high-level)
- Layers: config/app factory, extensions, domain models, repositories, services, parsing, web/API, templates/static. Source: [architecture](architecture.md).
- Repository + UnitOfWork pattern is mandatory for data access and transactional coordination; repositories encapsulate queries, UoW handles commit/rollback. Source: [architecture](architecture.md).
- Services orchestrate imports, invoices, payments, suppliers, categories, scans, and settings; parsing layer isolates FatturaPA extraction. Source: [architecture](architecture.md).

4) Database overview
- Single Table Inheritance with `documents` as supertype plus specialized tables (`invoice_lines`, `vat_summaries`, `rent_contracts`).
- Payments via `payments`, payment PDFs via `payment_documents`, links via `payment_document_links`.
- Logistics via `delivery_notes`; registries via `suppliers`, `legal_entities`; notes/import logs/settings/users included.
- Source of truth: [database](database.md).

5) Core workflows (user → system)
- Import: ingest XML/P7M, parse to DTOs, create suppliers/legal entities, documents, lines, VAT summaries, payments, delivery note expectations; log results.
- Review: filter/search documents, update statuses/due dates, categorize lines, manage notes.
- Physical copy: request/receive/upload scans tracked via `physical_copy_status` and storage paths.
- Payments: generate and update payment schedules, track statuses (`planned`, `pending`, `partial`, `paid`, etc.), import bank/payment PDFs, reconcile with `payment_document_links`.

6) Conventions & rules
- Single source of truth: prefer [docs/00_INDEX.md](00_INDEX.md) entrypoints plus [architecture](architecture.md) and [database](database.md).
- Extend existing layers (models → repositories → services → web/api) instead of duplicating logic; reuse DTOs and repos where possible.
- Keep diffs minimal; avoid refactors unless explicitly requested.

7) Plan → Work → Assess → Compound
- Plan: read INDEX + architecture + database; confirm scope and constraints; list touched components.
- Work: follow repository/UoW patterns; update services before routes/templates; keep changes localized.
- Assess: run sanity checks (import/review/payment flows) and lint if available; verify docs/links.
- Compound: capture learnings in docs; prefer reusable helpers over ad-hoc code.

8) Pre-merge checklist
- Run `python manage.py runserver` (dev) to ensure startup without errors.
- Smoke-test import/review/payment views if touched. TODO: add automated tests if available.

9) Known pitfalls
- Do not bypass repositories/UoW when accessing the DB.
- Maintain document_type compatibility; avoid schema tweaks without approval.
- Physical copy paths must align with settings/storage conventions.
- Keep P7M cleaning (control bytes + invalid tag bytes) and encoding fallback; use lxml recover only as last resort; prefer xsdata then legacy fallback.
- Payment status transitions must respect existing enums; reconcile via links, not ad-hoc joins.
- Delivery note matching differs for deferred invoices; preserve expected vs real DDT logic.
- Logging uses JSON with rotating file handler; avoid altering logging setup.
- Avoid duplicating category assignments; use existing service methods.
- Ensure supplier/legal entity uniqueness (VAT/fiscal codes) when importing.
- Payment module: il modello usa `due_date`, `expected_amount`, `notes`; servizi legacy potrebbero inviare `payment_date`, `amount`, `description`. Mappare sempre gli input sui campi corretti del Modello.
- Clean up temp/import folders cautiously; they drive audit logs.

10) Near-term TODOs
- Roadmap: implement F24/insurance/MAV-CBILL/affitti/scontrini/tasse flows and related imports per [roadmap/future_types.md](roadmap/future_types.md).
- Decluttering: follow `Cleaning_Plan.md` for low-risk cleanup and validation steps.
- OCR scans: fix Tesseract tessdata path/Italian language detection (TESSDATA_PREFIX) so scanned PDFs work reliably.
