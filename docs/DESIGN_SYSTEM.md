# Private Management Applications — Design System

Version 1.0 · 2026-09-07 · English instructions for AI coding agents

## 1. Purpose and authority

Build private, data-heavy management applications with the visual identity of Gestionale Acquisti: a compact dark top navigation, light gray canvas, white bordered panels, restrained blue actions, pastel status badges, dense readable tables, and practical document workflows.

This is a **normalized implementation specification**, not a pixel-exact snapshot. Follow the normative rules and starter code below when generating a new application. No access to the original repository is required. Keep user-facing language Italian by default; this specification is English to make reuse concise.

**Evidence labels:** **Observed** means present in the inspected source; **Normalized** means an explicit choice for consistency or to close a usability gap. All starter code is Normalized. It is intended for a new application; it is not a drop-in patch over the legacy CSS.

Priority: explicit product requirements → this specification → Bootstrap defaults. Domain entities, routes, permissions and calculations come from the new application's requirements. Do not copy purchasing-specific business rules merely to reproduce its appearance.

### Source coverage and limits

The audit inventories the application layers and all 31 HTML templates, 9 CSS files and 10 JavaScript files. Styling evidence comes from the shared shell, every stylesheet, template structure and inline styles, and interaction code. Architecture, application factory, template filters and number formatting establish integration boundaries. Generated invoice parser bindings and persistence code are not design authorities. This is a source-based frontend audit, not a line-by-line correctness audit of the backend. No authenticated browser session or live visual verification was performed.

| Source area | Design evidence / disposition |
|---|---|
| `base.html`, `compact.css` | Global navigation, cards, controls, tables, badges, flash alerts; retain identity, normalize conflicting overrides |
| `dashboard.html`, `dashboard.css` | Primary reference for hero, search, KPI cards, activity panels and spacing |
| `payments/index.html`, `payments.css`, `payments.js` | Primary reference for payment history, filters, expandable batches, pagination, new-payment workspace and confirmation |
| `payments/_invoice_list.html`, `schedule.html`, `schedule_print.html`, `detail.html`, `schedule.js` | Selection rows, financial totals, due dates, bulk actions, details and print |
| `documents/*`, document CSS/JS | Search/advanced filters, audit, review list, details, manual creation, attachments, matching, validation and split preview |
| `delivery_notes/*`, `delivery_notes.css` | List/detail/matching flows, compact data-entry panel and PDF preview |
| `suppliers/*`, `legal_entities/*`, `categories/*`, `categories_assign.js` | Registry lists/details, bank account data, editable categories and bulk assignment |
| `reports/index.html`, `reports.css` | Dashboard-compatible panels, SVG bars, CSS donut, legends and rankings |
| `import/import_run.html`, `import_batch.js`, `export/export_options.html` | Upload/progress/results and export configuration |
| `settings/edit.html`, `help/*` | Accordion settings, guide cards, steps and supporting information |
| `pdf_preview.css`, `pdf_upload_preview.js`, `ocr_badges.js`, `select_open.js` | PDF/text layers, OCR indicators and enhanced selects |
| `resources/xsl/*` (4 XSL files) | Invoice document rendering has its own typography/layout; isolate in the preview and do not import its styles into the application shell |
| `docs/00_INDEX.md`, `docs/architecture.md`, `docs/guides/payments_ui.md` | Architecture and historic UI intent; current CSS wins when documentation is stale |
| `app/__init__.py`, `app/web/template_filters.py`, `app/services/formatting_service.py` | Flask/Jinja integration and display formatting |

Paths above are provenance relative to the original repository, not dependencies of this document.

## 2. Stack and composition rules

**Observed:** Flask + Jinja2 server-rendered HTML, Bootstrap **5.3.0**, Bootstrap Icons **1.10.0**, jQuery **3.7.1**, Select2 **4.1.0-rc.0**, custom CSS and plain JavaScript. These versions describe the source baseline, not a recommendation about current releases. No frontend build pipeline is required for this design.

**Normalized implementation:**

1. Use a shared Jinja base with `title`, `extra_css`, `content`, `extra_js` blocks.
2. Load Bootstrap CSS, Bootstrap Icons, optional Select2 CSS, then `design-system.css`, then narrowly scoped page CSS.
3. Load Bootstrap bundle once. Load jQuery before Select2 only where enhanced selects are used. Load shared JS before page JS.
4. For private/offline installations, serve the pinned assets locally. Never depend on an unversioned CDN URL.
5. New components use `ds-` classes. Bootstrap owns its grid, collapse, modal, dropdown, tab, tooltip and pagination mechanics.
6. Do not copy `compact.css` wholesale alongside this starter: it globally redefines `.card`, `.badge`, `.btn-primary`, `.small` and other Bootstrap classes.
7. Presentation lives in templates/static assets; orchestration in services; persistence in repositories. Templates receive prepared display data. Frontend totals are previews; the server validates financial actions.
8. Extract repeated markup into Jinja macros/partials and shared interactions into JS modules. Keep visual constants in the token block.

## 3. Visual contract

- Use a full-width work surface. Desktop content padding is 24px, bottom 32px; mobile padding is 16px.
- Keep navigation charcoal and compact, expanded from 992px upward. No sidebar is part of this identity.
- Use white cards with 1px cool gray borders. Use 12px radii for major cards, 8px for embedded workspaces, 4px for controls, pill radii for statuses.
- Reserve the subtle pale gradient for a dashboard/report hero and selection summary. Operational pages start with a compact toolbar, not a large hero.
- Blue means interaction/selection. Green means successful/completed. Amber means attention/partial/pending review. Red means failure/overdue/missing required material. Gray means neutral/inactive/not required.
- Prefer one visually dominant action per local task group. Secondary actions are outlined. Use icons with labels.
- Favor compact spacing over small unreadable text. Show amounts and states before decorative content.
- Do not add decorative photos, oversized marketing headings, glass effects, decorative gradients, dark-mode variants or a new icon family unless requested.

### Deliberate normalization decisions

| Observed inconsistency | Canonical rule for new applications |
|---|---|
| Legacy primary `#007bff` vs Bootstrap/payment selection `#0d6efd` | Use `#0d6efd` throughout; hover `#0b5ed7`, active `#0a58ca` |
| Gray/slate text and several border families | Main text `#212529`, headings `#1f2d3d`, muted `#64748b`; panel border `#e2e8f0`, control border `#ced4da` |
| 8px global cards vs 12px dashboard/report cards | Major cards 12px; nested operational regions 8px |
| Global card padding plus Bootstrap card-body padding | Outer card has zero padding; header/body each own their padding |
| Legacy success/status palettes mixed with Bootstrap 5 tones | Use the semantic table below; preserve textual meaning |
| JavaScript copies page H1 into the brand and hides it | Render current section in navigation directly; keep one semantic H1; visually hide it only when it duplicates navigation |
| Payment history uses striped Bootstrap tables; dashboard uses compact tables | Use the compact table below; striping is optional for history and must not override status/selection |
| Payment split is `display:flex` but retains `grid-template-columns:1.6fr 1fr` | The grid declaration is inert. Current viewer basis is 38%; use actual flex sizing |
| Payment invoice grid minimum columns exceed narrow panels | Use a horizontally scrollable semantic table; never hide amount inputs with `overflow-x:hidden` |
| Media queries at 768, 991 and 992px | Normalize to `<768px`, `<992px`, `<1200px` using fractional max-width boundaries |
| Purple welcome banner / square menu helpers in shared CSS | Not the current dashboard reference; exclude from new designs |
| Browser alerts and partial keyboard handling | Use inline errors/status regions and accessible Bootstrap controls |
| Fixed action bars and hard-coded sticky offsets | Prefer normal-flow sticky toolbars; no overlap when labels wrap or the viewport is short |

## 4. Tokens

All rem-to-pixel equivalents assume a 16px browser default. Keep `html` at `100%` so user font preferences still work. Font is the system UI stack; the source does not load a custom webfont.

### Semantic colors

| Role | Background / base | Text | Border / accent |
|---|---|---|---|
| Page | `#f8f9fa` | `#212529` | — |
| Card | `#ffffff` | `#212529` | `#e2e8f0` |
| Heading | — | `#1f2d3d` | — |
| Muted / labels | — | `#64748b` / `#495057` | — |
| Navigation | `#212529` | `#ffffff` | — |
| Primary action | `#0d6efd` | `#ffffff` | `#0d6efd` |
| Body link | — | `#0b5ed7` | underline on hover |
| Success | `#d1e7dd` | `#0f5132` | `#a3cfbb` |
| Warning | `#fff3cd` | `#664d03` | `#ffe69c` |
| Danger | `#f8d7da` | `#842029` | `#f1aeb5` |
| Info | `#e7f1ff` | `#0b5ed7` | `#cfe2ff` |
| Neutral | `#e9ecef` | `#495057` | `#dee2e6` |
| Selected row | `#eff6ff` | normal text | `#0d6efd` |
| Expanded batch | `#f8fbff` | normal text | `#dbeafe` |
| Warning KPI | `#fffaf0` | normal heading | `#f8e3b2` |
| Danger KPI | `#fff5f5` | normal heading | `#f2c7c7` |

Use white text only on sufficiently dark solid action colors. Warning badges always use dark text. Status must also be written, never inferred only from color.

### Typography and dimensions

| Element | Size / weight | Geometry |
|---|---|---|
| Body / form input | `.95rem` (15.2px), 400 | line-height 1.5 |
| Visible page title | `2rem` (32px), 700 | line-height 1.2 |
| Hero title | `1.6rem` (25.6px), 700 | line-height 1.2 |
| Panel title | `1.05rem` (16.8px), 600 | line-height 1.3 |
| KPI value | `1.7rem` (27.2px), 700 | line-height 1.15 |
| Table body | `.9rem` (14.4px), 400 | cell padding `.5rem .75rem` |
| Table heading | `.8rem` (12.8px), 600 | uppercase, tracking `.5px` |
| Metadata / small control | `.85rem` (13.6px), 400 | line-height 1.5 |
| Field label | `.85rem`, 600 | margin-bottom `.25rem` |
| Compact filter label | `.75rem` (12px), 700 | allow wrapping |
| Eyebrow / KPI label | `.72rem` (11.52px), 700 | uppercase, tracking `.08em` |
| Status badge | `.8rem`, 600 | padding `.25rem .75rem`, pill |
| Default control/button | `.95rem` | min-height 40px; padding `.5rem .75rem` |
| Compact control/button | `.85rem` | min-height 34px; padding `.35rem .75rem` |
| Hero search / coarse pointer control | at least `.95rem` | min-height 44px |

Small uppercase text is only for short supplementary labels. Never put paragraph content or editable amounts at `.72rem`. Let rows grow when content wraps; do not enforce a fixed row height.

Spacing scale: `4, 8, 12, 16, 20, 24, 32px` (`.25, .5, .75, 1, 1.25, 1.5, 2rem`). Main section gap 24px; card grid gap 16px; dashboard panel gap 20px; action gap 8px. Retain the observed 17.6px horizontal KPI/card body padding (`1.1rem`) and 28px hero padding (`1.75rem`) as named component exceptions.

## 5. Reusable CSS foundation

Save this block as `app/static/css/design-system.css` in a new application. It assumes Bootstrap 5.3.0 is loaded first and `<body class="ds-app">`. No original project stylesheet is needed.

```css
:root {
  --ds-bg: #f8f9fa;
  --ds-surface: #fff;
  --ds-text: #212529;
  --ds-heading: #1f2d3d;
  --ds-muted: #64748b;
  --ds-label: #495057;
  --ds-border: #e2e8f0;
  --ds-control-border: #ced4da;
  --ds-primary: #0d6efd;
  --ds-primary-hover: #0b5ed7;
  --ds-primary-active: #0a58ca;
  --ds-success-bg: #d1e7dd;
  --ds-success-text: #0f5132;
  --ds-success-border: #a3cfbb;
  --ds-warning-bg: #fff3cd;
  --ds-warning-text: #664d03;
  --ds-warning-border: #ffe69c;
  --ds-danger-bg: #f8d7da;
  --ds-danger-text: #842029;
  --ds-danger-border: #f1aeb5;
  --ds-info-bg: #e7f1ff;
  --ds-info-text: #0b5ed7;
  --ds-info-border: #cfe2ff;
  --ds-neutral-bg: #e9ecef;
  --ds-neutral-text: #495057;
  --ds-neutral-border: #dee2e6;
  --ds-selected: #eff6ff;
  --ds-expanded: #f8fbff;
  --ds-space-1: .25rem;
  --ds-space-2: .5rem;
  --ds-space-3: .75rem;
  --ds-space-4: 1rem;
  --ds-space-5: 1.25rem;
  --ds-space-6: 1.5rem;
  --ds-space-8: 2rem;
  --ds-radius-control: 4px;
  --ds-radius-inner: 8px;
  --ds-radius-card: 12px;
  --ds-radius-hero: 14px;
  --ds-shadow: 0 2px 6px rgb(15 23 42 / 6%);
  --ds-shadow-hover: 0 6px 16px rgb(15 23 42 / 12%);
  --ds-list-height: 70vh;
  --ds-motion: 150ms ease;
  --bs-primary: #0d6efd;
  --bs-primary-rgb: 13, 110, 253;
  --bs-body-color: #212529;
  --bs-body-bg: #f8f9fa;
  --bs-link-color: #0b5ed7;
  --bs-link-hover-color: #0a58ca;
}
html { font-size: 100%; }
.ds-app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  margin: 0;
  background: var(--ds-bg);
  color: var(--ds-text);
  font: 400 .95rem/1.5 system-ui, -apple-system, "Segoe UI", Roboto,
    "Helvetica Neue", "Noto Sans", "Liberation Sans", Arial, sans-serif;
  font-variant-numeric: tabular-nums;
}
.ds-app main { flex: 1; min-width: 0; }
.ds-app .text-muted, .ds-meta { color: var(--ds-muted) !important; }
.ds-meta { font-size: .85rem; }
.ds-page { width: 100%; padding: 1.5rem 1.5rem 2rem; }
.ds-page-title { font-size: 2rem; line-height: 1.2; font-weight: 700; }
.ds-page-title, .ds-panel-title { color: var(--ds-heading); margin: 0; }
.ds-panel-title { font-size: 1.05rem; line-height: 1.3; font-weight: 600; }
.ds-toolbar, .ds-actions {
  display: flex; flex-wrap: wrap; align-items: center; gap: .5rem;
}
.ds-toolbar { justify-content: space-between; margin-bottom: 1rem; }
.ds-card {
  min-width: 0; padding: 0; background: var(--ds-surface);
  border: 1px solid var(--ds-border);
  border-radius: var(--ds-radius-card); box-shadow: var(--ds-shadow);
}
.ds-card-header {
  padding: 1rem 1.1rem; border-bottom: 1px solid var(--ds-border);
  display: flex; flex-wrap: wrap; align-items: center;
  justify-content: space-between; gap: .75rem;
}
.ds-card-body { padding: 1rem 1.1rem; }
.ds-hero {
  padding: 1.5rem 1.75rem; margin-bottom: 1.5rem;
  border: 1px solid #d9e2ef; border-radius: var(--ds-radius-hero);
  background: linear-gradient(135deg, #f7fafc, #eef3f9);
}
.ds-hero h2 { font-size: 1.6rem; font-weight: 700; color: var(--ds-heading); }
.ds-eyebrow, .ds-kpi-label {
  font-size: .72rem; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; color: var(--ds-muted);
}
.ds-search { display: flex; flex-wrap: wrap; gap: .65rem; }
.ds-search .form-control { flex: 1 1 280px; width: auto; min-width: 0; }
.ds-search .form-control, .ds-search .btn { min-height: 44px; }
.ds-kpis {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 190px), 1fr));
  gap: 1rem; margin-bottom: 1.5rem;
}
.ds-panels {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr));
  gap: 1.25rem;
}
.ds-kpi { display: block; padding: 1rem 1.1rem; color: inherit; text-decoration: none; }
.ds-kpi-value { margin: .35rem 0 .2rem; font-size: 1.7rem;
  line-height: 1.15; font-weight: 700; color: var(--ds-heading); overflow-wrap: anywhere; }
a.ds-kpi { transition: transform var(--ds-motion), box-shadow var(--ds-motion); }
a.ds-kpi:hover { color: inherit; transform: translateY(-2px); box-shadow: var(--ds-shadow-hover); }
.ds-kpi-warning { background: #fffaf0; border-color: #f8e3b2; }
.ds-kpi-danger { background: #fff5f5; border-color: #f2c7c7; }
.ds-app .btn { min-height: 40px; padding: .5rem .75rem; font-size: .95rem;
  font-weight: 500; border-radius: var(--ds-radius-control); }
.ds-app .btn-sm { min-height: 34px; padding: .35rem .75rem; font-size: .85rem; }
.ds-app .btn-primary {
  --bs-btn-bg: var(--ds-primary); --bs-btn-border-color: var(--ds-primary);
  --bs-btn-hover-bg: var(--ds-primary-hover); --bs-btn-hover-border-color: var(--ds-primary-hover);
  --bs-btn-active-bg: var(--ds-primary-active); --bs-btn-active-border-color: var(--ds-primary-active);
}
.ds-app .form-label { font-size: .85rem; font-weight: 600;
  color: var(--ds-label); margin-bottom: .25rem; }
.ds-app .form-control, .ds-app .form-select {
  min-height: 40px; font-size: .95rem; border-color: var(--ds-control-border);
  border-radius: var(--ds-radius-control);
}
.ds-app .form-control { padding: .5rem .75rem; }
.ds-app .form-select { padding: .5rem 2.25rem .5rem .75rem; }
.ds-app .form-control-sm, .ds-app .form-select-sm {
  min-height: 34px; font-size: .85rem; padding-top: .35rem; padding-bottom: .35rem;
}
.ds-app textarea.form-control { min-height: 96px; resize: vertical; }
.ds-app .form-control:focus, .ds-app .form-select:focus {
  border-color: #86b7fe; box-shadow: 0 0 0 .2rem rgb(13 110 253 / 20%);
}
.ds-app .form-control.is-invalid, .ds-app .form-select.is-invalid { border-color: #dc3545; }
.ds-app .form-control.is-valid, .ds-app .form-select.is-valid { border-color: #198754; }
.ds-app :focus-visible { outline: 2px solid var(--ds-primary); outline-offset: 2px; }
.ds-app .navbar :focus-visible { outline-color: #fff; }
.ds-filters {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: .75rem; align-items: end;
}
.ds-filters .form-label { font-size: .75rem; font-weight: 700; }
.ds-chips { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }
.ds-chip { display: inline-flex; align-items: center; gap: .35rem;
  padding: .25rem .6rem; border: 1px solid #dee2e6; border-radius: 999px;
  background: var(--ds-bg); color: var(--ds-label); font-size: .8rem; }
.ds-chip button { width: 24px; height: 24px; padding: 0; border: 0;
  border-radius: 50%; background: transparent; color: inherit; }
.ds-chip button:hover { background: #e9ecef; }
.ds-table-scroll { max-height: var(--ds-list-height); overflow: auto;
  scrollbar-gutter: stable; border-radius: var(--ds-radius-inner); }
.ds-table { width: 100%; margin: 0; border-collapse: separate;
  border-spacing: 0; font-size: .9rem; background: var(--ds-surface); }
.ds-table th, .ds-table td { padding: .5rem .75rem;
  border-bottom: 1px solid #dee2e6; vertical-align: middle; }
.ds-table th { position: sticky; top: 0; z-index: 2; background: var(--ds-bg);
  color: var(--ds-label); font-size: .8rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: .5px; text-align: left; }
.ds-table tbody tr:hover > td { background: var(--ds-bg); }
.ds-table tbody tr.ds-selected > td { background: var(--ds-selected); }
.ds-table tr.ds-selected > td:first-child { box-shadow: inset 3px 0 var(--ds-primary); }
.ds-table tr.ds-overdue > td { background: #fff5f5; }
.ds-table tr.ds-overdue:hover > td { background: #f8d7da; }
.ds-table tr.ds-selected.ds-overdue > td { background: var(--ds-selected); }
.ds-table tr.ds-expanded > td { background: var(--ds-expanded); }
.ds-table .ds-money { text-align: right; white-space: nowrap; }
.ds-table .ds-description { min-width: 12rem; overflow-wrap: anywhere; }
.ds-status { display: inline-flex; align-items: center; gap: .35rem;
  padding: .25rem .75rem; border-radius: 999px; font-size: .8rem;
  font-weight: 600; background: var(--ds-neutral-bg); color: var(--ds-neutral-text); }
.ds-status-success { background: var(--ds-success-bg); color: var(--ds-success-text); }
.ds-status-warning { background: var(--ds-warning-bg); color: var(--ds-warning-text); }
.ds-status-danger { background: var(--ds-danger-bg); color: var(--ds-danger-text); }
.ds-status-info { background: var(--ds-info-bg); color: var(--ds-info-text); }
.ds-status-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.ds-empty { padding: 2rem 1rem; text-align: center; color: var(--ds-muted);
  background: var(--ds-bg); border: 1px dashed var(--ds-border); border-radius: 10px; }
.ds-selection { padding: .7rem .9rem; border: 1px solid #cfe2ff; border-radius: 10px;
  background: linear-gradient(135deg, #eef6ff, #f8fbff); color: var(--ds-heading); }
.ds-selection strong { font-size: 1.2rem; line-height: 1.15; }
.ds-split { display: flex; align-items: stretch; gap: 1rem; min-width: 0; }
.ds-split-main { flex: 1 1 0; min-width: 0; }
.ds-split-preview { flex: 0 1 38%; min-width: 0; }
.ds-preview { display: block; width: 100%; height: 70vh;
  border: 1px solid var(--ds-border); border-radius: 8px; background: #fff; }
.ds-app .nav-tabs .nav-link { padding: .35rem .75rem; font-size: .9rem; }
.ds-app .modal-content { border-radius: 12px; }
.ds-app .modal-header, .ds-app .modal-body, .ds-app .modal-footer { padding: 1rem; }
.ds-app .alert { border-radius: 4px; margin-bottom: 1rem; }
.ds-app .alert:not(.alert-dismissible) { padding: 1rem; }
.ds-footer { padding: 1rem; border-top: 1px solid var(--ds-border);
  color: var(--ds-muted); font-size: .85rem; text-align: center; }
@media (max-width: 991.98px) {
  .ds-split { flex-direction: column; }
  .ds-split-preview { flex-basis: auto; }
}
@media (max-width: 767.98px) {
  .ds-page { padding: 1rem; }
  .ds-hero { padding: 1.25rem; }
  .ds-search { flex-direction: column; }
  .ds-search .form-control { flex-basis: auto; width: 100%; }
  .ds-search .btn { width: 100%; }
  .ds-filters { grid-template-columns: 1fr; }
  .ds-toolbar { align-items: flex-start; }
  .ds-table { font-size: .85rem; }
  .ds-table th, .ds-table td { padding: .35rem .5rem; }
  .ds-selection { width: 100%; }
}
@media (pointer: coarse) {
  .ds-app .btn, .ds-app .form-control, .ds-app .form-select { min-height: 44px; }
  .ds-app .form-control, .ds-app .form-select { font-size: 1rem; }
  .ds-chip button { width: 44px; height: 44px; }
}
@media (prefers-reduced-motion: reduce) {
  .ds-app *, .ds-app *::before, .ds-app *::after {
    animation: none !important; transition: none !important; scroll-behavior: auto !important;
  }
  a.ds-kpi:hover { transform: none; }
}
```

## 6. Shared Jinja shell

Minimal runnable layout once vendor assets are supplied. Paths under `vendor/` are target filenames to populate, not files claimed to exist in the source. Views provide `page_title`, `home_url` and `navigation` entries with `label`, `url`, `active`. Use explicit routes generated with `url_for` in the application. Supply unique titles and escape all user content.

```html
<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}{{ page_title }} | Gestionale{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/bootstrap-5.3.0.min.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/bootstrap-icons-1.10.0/bootstrap-icons.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/design-system.css') }}">
  {% block extra_css %}{% endblock %}
</head>
<body class="ds-app">
  <a class="visually-hidden-focusable p-2" href="#main">Vai al contenuto</a>
  <nav class="navbar navbar-expand-lg navbar-dark bg-dark py-1" aria-label="Principale">
    <div class="container-fluid">
      <a class="navbar-brand fw-bold" href="{{ home_url }}">
        <i class="bi bi-box-seam me-1" aria-hidden="true"></i>{{ page_title }}
      </a>
      <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
        data-bs-target="#main-nav" aria-controls="main-nav" aria-expanded="false"
        aria-label="Apri navigazione"><span class="navbar-toggler-icon"></span></button>
      <div class="collapse navbar-collapse" id="main-nav">
        <ul class="navbar-nav me-auto">
          {% for item in navigation %}
          <li class="nav-item"><a class="nav-link{% if item.active %} active{% endif %}"
            href="{{ item.url }}"{% if item.active %} aria-current="page"{% endif %}>{{ item.label }}</a></li>
          {% endfor %}
        </ul>
      </div>
    </div>
  </nav>
  <main id="main" tabindex="-1">
    <div class="ds-page">
      <h1 class="visually-hidden">{{ page_title }}</h1>
      {% for category, message in get_flashed_messages(with_categories=true) %}
        {% set tone = {'error':'danger', 'danger':'danger', 'warning':'warning',
                       'success':'success'}.get(category, 'info') %}
        <div class="alert alert-{{ tone }} alert-dismissible fade show"
             role="{{ 'alert' if tone in ['danger', 'warning'] else 'status' }}">
          {{ message }}
          <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Chiudi"></button>
        </div>
      {% endfor %}
      {% block content %}{% endblock %}
    </div>
  </main>
  <footer class="ds-footer">Gestionale interno</footer>
  <script src="{{ url_for('static', filename='vendor/bootstrap-5.3.0.bundle.min.js') }}"></script>
  {% block extra_js %}{% endblock %}
</body>
</html>
```

The shell uses a hidden H1 because navigation already presents the section name. For detail pages with a unique record title, make this H1 visible using `ds-page-title mb-3` and supply the record title. Do not create an additional H1 in the content block. Group larger navigation trees into Bootstrap dark dropdowns; put Help and Settings at the right with `ms-auto`. Preserve active-state text/ARIA when using dropdowns.

## 7. Component recipes

### Dashboard

Order: hero with short context → search and shortcuts → KPI grid → upcoming work and recent activity. Use 4 KPI cards when the domain supports four useful measures. Values link to the corresponding filtered list. Never invent metrics to fill the grid.

```html
{% extends "base.html" %}
{% block content %}
<section class="ds-hero" aria-labelledby="overview-title">
  <div class="ds-eyebrow">Panoramica</div>
  <h2 id="overview-title">Controllo delle attività</h2>
  <p class="ds-meta">Scadenze, documenti e operazioni recenti.</p>
  <form method="get" action="{{ list_url }}">
    <label for="dashboard-q" class="form-label">Cerca documenti</label>
    <div class="ds-search">
      <input id="dashboard-q" name="q" type="search" class="form-control"
             placeholder="Numero, fornitore, descrizione" required>
      <button class="btn btn-primary" type="submit">
        <i class="bi bi-search" aria-hidden="true"></i> Cerca
      </button>
      <a class="btn btn-outline-secondary" href="{{ list_url }}">Filtri avanzati</a>
    </div>
  </form>
</section>
<section class="ds-kpis" aria-label="Indicatori principali">
  {% for kpi in kpis %}
  <a class="ds-card ds-kpi{% if kpi.tone in ['warning','danger'] %} ds-kpi-{{ kpi.tone }}{% endif %}"
     href="{{ kpi.url }}">
    <div class="ds-kpi-label">{{ kpi.label }}</div>
    <div class="ds-kpi-value">{{ kpi.value_display }}</div>
    <div class="ds-meta">{{ kpi.meta }}</div>
  </a>
  {% endfor %}
</section>
{% endblock %}
```

Provide `list_url` and `kpis` from the view. Add `ds-panels` below for activity lists and compact upcoming-item tables. Activity items use `padding:.65rem .75rem`, `gap:.75rem`, `border:1px solid #eef2f7`, `background:#fafbfc`, `border-radius:10px`. Let names wrap; metadata is `.85rem`. Use an empty message within the affected panel when no records exist.

### List / payment history — primary operational reference

Order: compact actions → optional tabs → filter card → result count and active-filter chips → table → pagination. Payment history starts selected; new payment is a separate tab. History columns: payment date, document/batch, supplier, paid amount, method, account, status, actions.

- Put filter and search values in GET parameters. Preserve them through sorting, pagination, detail/back navigation and exports.
- Keep search visible. Advanced filters may collapse behind a labeled button with `aria-expanded` and `aria-controls`.
- Show date range, account and method filters in 4 columns at ≥992px, 2 at ≥576px and 1 below 576px (`col-12 col-sm-6 col-lg-3`).
- Show `1–25 di 120` and a clear reset action. An empty filtered result must offer clearing filters, not imply the database is empty.
- Use one scroll container capped at 70vh with a flush sticky table header. Detail-table variants may cap at 55vh.
- Keep text left-aligned, amounts right-aligned with tabular numerals, dates unbroken. Never truncate an amount or an editable control.
- Expand batches with a real button, chevron rotation 90°, `aria-expanded`, `aria-controls`; nest a compact table on `#f8fbff` with `#dbeafe` separators. Put the collapsed region inside a full-width table cell, not a non-table element directly inside `tbody`.
- Optional history stripes use `#fafbfc`. Priority: selected → overdue → expanded → hover → stripe → white. Keep status text visible even when selection overrides its background.
- Use a link in the identifying cell. A clickable whole row is an optional pointer convenience, never the only way to open a record.
- Pagination uses Bootstrap `pagination-sm`, `aria-current="page"` for the current page, and noninteractive spans for unavailable previous/next actions.

Reusable table; context is `rows` with `id`, `url`, `label`, `party`, `amount_display`, `status_label`, `tone` and `selected`:

```html
<section class="ds-card" aria-labelledby="results-title">
  <header class="ds-card-header">
    <h2 class="ds-panel-title" id="results-title">Elenco pagamenti</h2>
    <span class="ds-meta">{{ result_count_display }} voci</span>
  </header>
  <div class="ds-table-scroll" role="region" aria-label="Tabella pagamenti" tabindex="0">
    <table class="ds-table">
      <caption class="visually-hidden">Pagamenti corrispondenti ai filtri</caption>
      <thead><tr><th scope="col">Documento</th><th scope="col">Fornitore</th>
        <th scope="col" class="ds-money">Importo pagato</th><th scope="col">Stato</th></tr></thead>
      <tbody>
        {% for row in rows %}
        <tr{% if row.selected %} class="ds-selected"{% endif %}>
          <td><a href="{{ row.url }}">{{ row.label }}</a></td>
          <td class="ds-description">{{ row.party }}</td>
          <td class="ds-money">{{ row.amount_display }}&nbsp;€</td>
          <td><span class="ds-status{% if row.tone in ['success','warning','danger','info'] %} ds-status-{{ row.tone }}{% endif %}">
            <span class="ds-status-dot" aria-hidden="true"></span>{{ row.status_label }}</span></td>
        </tr>
        {% else %}
        <tr><td colspan="4"><div class="ds-empty">Nessun risultato per i filtri selezionati.</div></td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</section>
```

This snippet does not imply client sorting or selection logic. Add controls and server parameters when those features are required. Sort headers must expose a button/link and set `aria-sort` on the currently sorted `th`.

### Forms, filters and enhanced selects

Use permanent labels, helper text below the field, explicit required indicators and inline validation. Placeholder text supplements the label. Group related fields into a panel; use Bootstrap `row g-2` for compact forms, `g-3` for longer forms. Default textarea minimum is 96px; a dense review-only variant may be 64px.

```html
<div class="mb-3">
  <label class="form-label" for="payment-amount">Importo pagato (obbligatorio)</label>
  <div class="input-group">
    <span class="input-group-text" id="payment-currency">€</span>
    <input id="payment-amount" name="amount" type="number" min="0" step="0.01"
      required class="form-control text-end{% if amount_error %} is-invalid{% endif %}"
      value="{{ amount_raw }}" aria-describedby="payment-currency amount-help{% if amount_error %} amount-error{% endif %}"
      {% if amount_error %}aria-invalid="true"{% endif %}>
  </div>
  <div id="amount-help" class="form-text">Inserisci l'importo da registrare.</div>
  {% if amount_error %}<div id="amount-error" class="invalid-feedback d-block">{{ amount_error }}</div>{% endif %}
</div>
```

`amount_raw` must be a machine-readable decimal with a dot, never a localized display string. `amount_error` is a server-validated error. Validation state uses `.is-invalid`, `aria-invalid` and a meaningful error message; preserve entered values after failure.

Select2 is optional for long searchable registries. Simple short choices use native selects. When enabled, load its CSS before design-system CSS; initialize only once; use `dropdownParent` for selects in a modal. Match single-select height 40px, border `#ced4da`, radius 4px and text `.95rem`; compact variant 34px; multi-select grows with wrapping chips. Verify keyboard interaction and associated labels. Never apply the 40px fixed height to a multi-select.

```javascript
function enhanceSelects(root = document) {
  if (!window.jQuery?.fn.select2) return;
  jQuery(root).find('select.js-select2').each(function () {
    const field = jQuery(this);
    if (field.data('select2')) return;
    const modal = field.closest('.modal');
    field.select2({ width: '100%', ...(modal.length ? { dropdownParent: modal } : {}) });
  });
}
document.addEventListener('DOMContentLoaded', () => enhanceSelects());
```

### Status mapping

Map domain states to tones in one presentation mapping; do not make raw status strings CSS class names. Unrecognized states use a neutral badge with a meaningful fallback label.

| Meaning | Tone | Example Italian labels |
|---|---|---|
| Completed / verified / received / paid | success | Verificato, Ricevuto, Pagato |
| Partial / needs review / requested | warning | Parziale, Da rivedere, Richiesto |
| Overdue / rejected / required copy missing | danger | Scaduto, Rifiutato, Copia mancante |
| Informational / waiting on supporting material | info | In attesa di copia |
| Archived / not required / no classification | neutral | Archiviato, Non richiesto |

Observed legacy `unpaid` is red. Normalize ordinary not-yet-due unpaid records to neutral/info; reserve danger for overdue or otherwise actionable problems. This changes visual emphasis, not domain state or accounting behavior.

### Selection and bulk confirmation

Display a checkbox with an accessible record-specific label. Clicking embedded links or amount fields must not toggle the row. Define whether “select all” applies to the current page or every filtered result; show the scope explicitly. Retain selections across pagination only if supported and communicated.

Place count and totals in `ds-selection`. For the source payment pattern, show three separate amounts: selected documents, applied credit, net bank payment. Do not compress these into one ambiguous number. Disable the submit action when no valid selection exists; show why nearby.

Use Bootstrap `modal-lg modal-dialog-scrollable` for batch confirmation: short title, count/date/account summary, grouped supplier rows, net total, secondary Cancel and primary Confirm. Ordinary confirmation uses `modal-dialog` (500px default maximum); batch uses `modal-lg` (800px at applicable desktop widths). Let Bootstrap handle backdrop and stacking. Mobile dialog uses `modal-fullscreen-sm-down` for complex reviews.

Initialize the modal using Bootstrap. Provide `aria-labelledby`, a labeled close button, focus inside on open and focus restoration on close. Summary cards use 12px gaps, 12px padding, 10px radius, `#f8fbff` background and `#dbeafe` border. Destructive confirmation uses danger styling and names the affected record. Successful operations must be acknowledged only after server success.

### Tabs and accordions

Use Bootstrap tabs with button triggers, `role="tablist"`, `role="tab"`, `aria-controls`, `aria-selected`, linked tab panels and unique IDs. Initialize via `data-bs-toggle="tab"`; do not combine independent tab engines. If URLs preserve the selected tab, validate the hash against known panel IDs. Verify arrow-key traversal and focus behavior in the pinned version.

Accordions group settings and details. Header padding `.75rem 1rem`, 600 weight, collapsed background `#f8f9fa`, expanded `#eef2f7`, border `#dee2e6`, body padding `.75rem`. Use real heading elements and Bootstrap collapse buttons. Keep critical validation errors outside a closed accordion or open the affected section automatically.

### Document/PDF workspace

At ≥992px, use `ds-split` with the form first and a 38% preview basis. At smaller widths, stack preview below the form. The source review workspace instead uses 55% preview; keep this only as an explicit review modifier. Viewer height is 70vh and should have a loading/empty/error state plus an “Open PDF” link. Always give iframes a descriptive `title`.

**Optional resizer:** observed payment handle is 8px wide with `.4rem` side margins and a 2×48px grip; review uses 12px and a 4×56px grip. Normalize to a keyboard-focusable separator with `role="separator"`, vertical orientation, range/value ARIA, ArrowLeft/ArrowRight steps, and pointer capture. Clamp preview to 25–70% only while both panels retain useful width; hide the handle below 992px. Never include a handle that has no working keyboard/pointer implementation. The starter intentionally uses a fixed ratio and no handle.

For invoice selection, the observed desktop grid is `42px 120px minmax(140px,1fr) 140px 110px 150px`, gap `.35rem`; widths reduce at 1199px and 991px. This requires roughly 754px including gaps/padding even before a viewer is added. In the normalized design use a table with `min-width:48rem` inside `ds-table-scroll`, or an explicitly implemented labeled mobile card view. Horizontal scrolling is contained in the list, never the page. Keep a single authoritative input per record.

PDF upload shows accepted type and size limits sourced from the backend, selected filename, progress, readable failure and retry. The source has PDF-only/10MB checks in some clients; these are workflow-specific, not design tokens. Never assume every new application has the same limit.

OCR assist uses a small info badge (`#e0f2fe`/`#0369a1`), low-confidence warning (`#fef3c7`/`#92400e`), and a field border `#38bdf8`. Include visible text such as “Da verificare”; distinguish suggested data from confirmed saved data. PDF text highlights use `#fff3b0` with an inset `#f2c94c` border. OCR outlines must not hide keyboard focus or validation errors.

### Details, settings, import, help and reports

| Screen | Composition and exact reusable choices |
|---|---|
| Record detail | Compact title/context/actions; summary grid with minimum 220px columns; 12px gaps; summary items min-height 64px, radius 8px; details in accordions; related tables capped at 55vh |
| Registries | Filter/search + table; detail uses label/value pairs and bank/contact sections; text wraps, identifiers remain copyable |
| Categories | Editable list and bulk assignment; selected count and clear save action; neutral category chips |
| Settings | Topic accordions, short field explanations, explicit save result; narrow prose measure about 72ch, forms may use full available grid |
| Import | File picker + supported format guidance + primary upload; progress bar and processed/error counts; result summary with retryable failures |
| Export | Filter form and explicit format/action; preserve source filters; show preparing state without blocking unrelated navigation |
| Help | Searchable guide cards; short introduction, prerequisites, ordered steps and completion check; reading column max-width 72ch |
| Reports | Same hero and KPI identity; 20px panel gaps; no separate visual theme |

Reports in the source use native SVG bars and a CSS donut, not Chart.js. Preserve that lightweight approach when adequate. Bar chart source colors are positive `#1f6f43`, negative `#b42318`, axis `#cbd5e1`, labels `#475569` at 12px. The effective report SVG minimum width is 560px and height 210px (later rules override 480px/150px). Put it in a horizontally scrollable region on narrow screens. Donut diameter ≤220px, hole inset 24%, legend gap `.7rem`, swatches `.85rem`. A normalized categorical palette is `#0d6efd`, `#1f6f43`, `#6f42c1`, `#b45309`, `#087990`, `#64748b`; assign colors consistently by category and include text labels/values. This categorical palette is a proposed standard, not a source extraction. Use green/red for financial meaning only where the metric supports that meaning; increases in expenses are not automatically good.

Provide a text/table equivalent for charts, visible units, period and a concise takeaway. Do not rely on hover-only tooltips or color alone.

## 8. Interactive states and accessibility

These are normative product requirements, not claims that the source already satisfies them. Validate contrast and keyboard behavior in the generated application.

| State | Required treatment |
|---|---|
| Default | Clear label, role and action; no hover required to discover essential actions |
| Hover | Blue action darkens; linked KPI rises 2px; row background changes gently |
| Focus | Visible 2px blue outline, 2px offset; white outline on dark navigation; no global outline removal |
| Active | Primary uses `#0a58ca`; current nav/page/tab carries ARIA state |
| Selected | Pale blue row + 3px blue leading indicator + checked checkbox |
| Disabled | Native `disabled` for controls, Bootstrap disabled appearance; explain prerequisites nearby; a disabled link must also be noninteractive |
| Loading | Keep button label meaningful, small spinner, prevent duplicate submission, `aria-busy` on affected region |
| Success | Inline status/flash after server acknowledgement, success tone; preserve route/context |
| Error | Specific inline message with recovery action; preserve inputs, restore buttons; focus error summary for submit errors |
| Empty | Distinguish no data / no filtered matches / no selection; offer the relevant next action |
| Read-only | Values remain legible and selectable; communicate why editing is unavailable |

The source dismisses success/info flashes after 4500ms. Normalized default is persistent dismissible feedback. Auto-dismiss may be used only for redundant nonessential confirmations, with sufficient time and pause on hover/focus; errors and warnings stay visible until resolved/dismissed.

Use semantic headings in order; associate every input with a label; mark decorative icons `aria-hidden="true"`; give icon-only buttons names. Keep at least 24×24px isolated action targets and 44px controls for coarse pointers. Mobile form font becomes 16px to improve entry. Test 200% zoom, long labels and keyboard-only use. Announce asynchronous counts/summaries using a stable `role="status"` region. Do not announce every keystroke in a live amount field.

Minimal async button-state helper (call around an application's actual request; it does not send data):

```javascript
async function withBusy(button, region, status, task) {
  if (button.disabled) return;
  const saved = [...button.childNodes].map(node => node.cloneNode(true));
  const spinner = document.createElement('span');
  spinner.className = 'spinner-border spinner-border-sm me-1';
  spinner.setAttribute('aria-hidden', 'true');
  button.disabled = true;
  button.replaceChildren(spinner, document.createTextNode(' Elaborazione…'));
  region.setAttribute('aria-busy', 'true');
  status.textContent = 'Operazione in corso.';
  try {
    await task(); // Must reject on HTTP/application failure, not only network errors.
    status.textContent = 'Operazione completata.';
  } catch (error) {
    status.textContent = 'Operazione non completata. Controlla i dati e riprova.';
    throw error; // Caller handles detailed validation errors; avoid unhandled rejections.
  } finally {
    button.replaceChildren(...saved);
    button.disabled = false;
    region.removeAttribute('aria-busy');
  }
}
```

Use `textContent` for user-provided strings. Server-rendered HTML fragments must remain escaped. Use event delegation or idempotent setup after replacing partials; do not accumulate handlers. Handle aborted/stale search requests so older results cannot overwrite newer filters. Store only appropriate UI preferences under namespaced keys; do not persist confidential record contents just to remember layout.

## 9. Responsive contract

| Width | Required behavior |
|---|---|
| `<576px` | Single-column forms; primary search controls full width; complex modals full screen; horizontal scrolling limited to tables/charts |
| `576–767.98px` | Simple filter pairs may use 2 columns; advanced dense filter grid remains 1 column; actions wrap |
| `768–991.98px` | 24px page padding; adaptive cards; navigation collapsed; form/preview stacked |
| `992–1199.98px` | Expanded navbar; form/preview side by side; table scroll remains available |
| `≥1200px` | Full desktop workspace; no arbitrary max-width on data pages; wrap oversized content within cards |

Use `min-width:0` on flex/grid children and `minmax(0,1fr)` for flexible tracks. A fixed minimum must never force the whole page wider than the viewport. Use `minmax(min(100%,Npx),1fr)` for auto-fit card grids. Preserve all information when a table cannot compress; do not “fix” overflow by clipping it.

On mobile, sticky filter/bulk bars become static. On desktop, if multiple bars must stick, measure the preceding bar height or place them in one sticky wrapper; do not assume a constant 3.4rem offset. A fixed review footer requires bottom padding equal to its actual height and must not cover controls. Prefer normal flow where possible.

Check short viewports as well as narrow ones. Do not set fixed `100vh` panels beneath an unmeasured navigation bar. For a full-height review workspace, use a flex column with a measured/in-flow header and `min-height:0` on the scroll region.

## 10. Formatting, print and motion

**Observed numeric behavior:** `format_amount` emits two decimal places. When grouping is enabled it emits Italian separators (`1.234,56`); when disabled it emits a dot decimal (`1234.56`). Do not claim the source always formats Italian decimals.

**Normalized:** choose one display policy centrally for each new application; default Italian UI displays `1.234,56 €`, dates `07/09/2026`, timestamps `07/09/2026 14:05`, negative amounts `-123,45 €`, missing data `—` and actual zero `0,00 €`. Raw input/API values use ISO dates and ungrouped dot decimals. Never derive financial totals by parsing localized strings or use floating-point display calculations as authoritative accounting. Make rounding policy a backend concern.

Print is a separate dense layout. **Observed** schedule print uses Arial, pale table headers and semantic pastel badges. **Normalized** print recipe: Arial 10pt, title 16pt, section title 12pt, cell padding 4pt 6pt, white background, no shadows/navigation/buttons, 12mm page margins; A4 landscape for wide schedules, portrait for narrow detail reports. Repeat `thead`, avoid breaking short rows, remove scroll-height limits, include generation date/filter summary and display all amounts. Verify rendering with the actual print/PDF engine before shipping; colors alone must not carry meaning in grayscale.

Motion is functional: 150ms color/shadow/transform transitions, ≤2px linked-card lift, 90° disclosure chevron rotation. No page entrance animations or automatic scrolling without purpose. Respect reduced-motion preferences, including chart and spinner behavior.

## 11. Agent implementation and acceptance checklist

Before coding, identify the required screen families and reuse the matching recipes. Implement tokens and the base shell first, then shared components, then domain screens. Only page layout differences belong in page CSS. When adapting a legacy project, inspect its CSS cascade before adding this foundation.

- [ ] Pin and load dependencies in the stated order; no duplicate Bootstrap/Select2 initialization.
- [ ] Dark compact top navigation, pale canvas, white 12px cards and one coherent primary blue.
- [ ] All repeated visual values use tokens or documented component exceptions.
- [ ] Dashboard uses short hero, working search, real KPIs and meaningful empty panels.
- [ ] Lists include filter persistence, count, sorting state, contained scrolling and accessible pagination.
- [ ] Numeric cells align right; amounts and controls are never clipped; long names and IBANs remain accessible.
- [ ] Selection count, scope and totals agree; links/inputs do not accidentally toggle selection.
- [ ] Validate default, hover, focus, active, selected, disabled, loading, success, error and empty states.
- [ ] Test keyboard navigation, modal close/focus return, tabs, accordion, enhanced selects and optional splitter.
- [ ] Test at 360, 390, 768, 991, 992, 1199, 1200, 1440 and 1920px, plus a short 600px-high viewport and 200% zoom.
- [ ] No body-level horizontal scrollbar; only intended tables/charts scroll horizontally.
- [ ] Test empty datasets, long Italian labels, large/negative/zero amounts, missing dates and many status badges.
- [ ] Simulate slow requests, server validation failure, network failure and repeated clicks; preserve input and restore controls.
- [ ] Check text/control contrast using computed colors; do not treat the palette alone as proof of accessibility.
- [ ] Print a wide table; inspect repeated headings, clipped columns, grayscale meaning and page breaks.
- [ ] Capture desktop/mobile screenshots of dashboard, payment-style history and a form/preview screen using synthetic data.
- [ ] Keep services/repositories, database schemas, configuration and logging outside a styling-only change.

### Compact instruction to reuse with an AI agent

> Implement the requested private management application using this document as the canonical frontend specification. Use Flask/Jinja, Bootstrap 5 and Bootstrap Icons. Reuse the normalized CSS tokens, shell and component recipes. Match the dashboard and payment-history visual hierarchy: compact dark top navigation, light gray page, white bordered cards, blue actions, pastel semantic statuses and readable dense tables. Preserve all data and controls on small screens through contained scrolling and stacking. Implement accessible interactive states and server-authoritative validation. Do not reproduce legacy CSS conflicts or introduce an unrelated design language. Report any deliberate deviation and verify the acceptance checklist with synthetic data.
