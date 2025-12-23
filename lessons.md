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

## FatturaPA / Parsing & P7M
- Use xsdata as primary path with legacy fallback; log when fallback is used.
- Clean tag names with non-ASCII bytes before parsing to avoid missing bodies.
- Keep encoding fallback (cp1252/latin-1); use recover only as last resort; dump to `import_debug/p7m_failed/`.

## Error Fixes
- Watch for double `{% endblock %}` and missing imports when adding template features.
- Compute complex URLs (with dynamic kwargs) in the route/controller and pass them to templates to avoid Jinja syntax issues.
