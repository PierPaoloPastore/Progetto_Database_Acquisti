# Lessons Learned

## DDT (Delivery Notes)
- `delivery_note_lines` table already exists; add SQLAlchemy model, repo/UoW, and service upsert/list helpers to manage lines without changing schema.
- Matching is intentionally permissive: DDT can be linked to a document if they share the same supplier; number/date are optional filters. Keep invoices as the accounting source of truth.
- Bidirectional matching is useful: from invoice (detail/review) to DDT and from DDT to invoice. Warn/guard if needed when re-linking DDT already matched elsewhere.
- DDT remain valid without lines; amounts on lines stay optional (header is primary).

## Review Flow
- Add DDT matching and physical copy upload directly in the review page via separate actions to avoid breaking the main confirm flow.
- Show linked DDT and candidates in the review UI to reduce context switching.
- Physical copy upload during review should reuse existing services; provide quick access to view the file if already attached.

## UI Patterns
- For sticky table headers, remove padding from the scroll wrapper to avoid visible gaps between thead and container shadow.
- Sorting with query params (`sort`/`dir`) keeps filters intact; clickable headers should show state via caret icons and link styles.
- Keep changes minimal: prefer small CSS tweaks and server-side sorting over heavy JS refactors.
- For list containers with sticky thead, use a “flush” scroll wrapper (padding 0) to avoid the white gap between header and card/shadow; apply consistently to new lists (documents, payments, scadenziario, etc.).
- For grouped schedule views, precompute status/amounts once in the route and pass normalized rows to templates to keep filters consistent.
- Keep raw numeric values for URLs and `data-*` attributes; apply formatting only to visible text.
- When reorganizing settings UI into accordions, preserve input `id` and `data-clip-target` hooks so existing JS keeps working.

## Settings & Formatting
- Store toggle settings as "0"/"1" strings in `AppSetting`, then normalize to bool in routes to avoid drift.
- Centralize number formatting in a single helper and expose it as Jinja filters for UI and export consistency.

## FatturaPA / Parsing & P7M
- Use xsdata as primary path with legacy fallback; log when fallback is used.
- Clean tag names with non-ASCII bytes before parsing to avoid missing bodies.
- Normalize XML bytes before xsdata; if root parsing fails, try encoding fallback then legacy parser.
- Keep encoding fallback (cp1252/latin-1); use recover only as last resort; dump to `import_debug/p7m_failed/`.

## Cleanup / Maintenance
- Before deleting templates/static, confirm `render_template` references and Jinja includes/extends.
- Check `base.html` for shared CSS/JS before removing assets.
- Remove legacy service helpers only after repo-wide reference scan.

## Error Fixes
- Watch for double `{% endblock %}` and missing imports when adding template features.
- Compute complex URLs (with dynamic kwargs) in the route/controller and pass them to templates to avoid Jinja syntax issues.
