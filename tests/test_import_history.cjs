// Run: node tests/test_import_history.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const handlers = {};
const rows = [
    { dataset: { category: "problems" }, textContent: "bad.xml Fornitore A" },
    { dataset: { category: "success" }, textContent: "good.xml Fornitore B" },
    { dataset: { category: "duplicate" }, textContent: "old.xml Fornitore C" },
];
const select = { value: "all", options: ["all", "problems", "success", "duplicate", "warning"].map(
    value => ({ value, textContent: value, dataset: {} })),
    addEventListener: (type, fn) => handlers[type] = fn };
const search = { value: "", addEventListener: (type, fn) => handlers[type] = fn };
const count = {};
const section = {
    querySelector: selector => ({ "[data-outcome-filter]": select, "[data-detail-search]": search,
        "[data-detail-count]": count })[selector] || rows.find(r => r.dataset.category === "problems"),
    querySelectorAll: () => rows,
    addEventListener: (type, fn) => handlers[type] = fn,
};
vm.runInNewContext(fs.readFileSync("app/static/js/import_history.js", "utf8"), {
    document: { addEventListener: (_, fn) => fn(), querySelectorAll: () => [section] },
});
assert.equal(select.value, "problems");
assert.equal(count.textContent, "1 di 3 file mostrati");
assert.deepEqual(rows.map(r => r.hidden), [false, true, true]);
select.value = "all"; search.value = "fornitore b"; handlers.input();
assert.deepEqual(rows.map(r => r.hidden), [true, false, true]);
search.value = "missing"; handlers.input();
assert.equal(count.textContent, "0 di 3 file mostrati");
rows.push({ dataset: { category: "warning" }, textContent: "archive warning" });
handlers["import-details-updated"]();
assert.equal(search.value, "");
assert.equal(select.options[0].textContent, "all (4)");
assert.equal(select.options[4].textContent, "warning (1)");
console.log("OK: default problems, search, categories, empty results and refreshed counts.");

class Element {
    constructor() { this.children = []; this.dataset = {}; this.style = {}; this.classList = { remove() {}, add() {} }; }
    appendChild(child) { this.children.push(child); }
    dispatchEvent() { this.refreshed = true; }
}
const batchSource = fs.readFileSync("app/static/js/import_batch.js", "utf8");
const renderCode = batchSource.slice(batchSource.indexOf("    const renderSummary ="), batchSource.indexOf("    const recoveryLink ="));
const body = new Element(); const list = new Element();
const context = { document: { createElement: () => new Element() }, Event,
    summaryCard: new Element(), summaryErrorsBody: body, summaryErrorsList: list,
    summaryTotal: null, summaryImported: null, summarySkipped: null, summaryWarnings: null,
    summaryErrors: null, summaryNarrative: null, summaryReport: null, summaryReportLink: null,
};
vm.createContext(context);
vm.runInContext(renderCode + "\nglobalThis.render = renderSummary;", context);
const detail = { status: "skipped", status_label: "Già presente", invoice_id: 7,
    document_number: "A/1", document_date: "2026-10-31", document_url: "/documents/7",
    existing_imported_at: "03/11/2026 12:43:00 UTC", message: "Già presente" };
context.render({ file_groups: [{ file_name: "safe&name.xml", category: "duplicate", tone: "secondary",
    label: "Già presente", details: [detail, { ...detail, document_number: "A/2" }] }] }, [detail]);
assert.equal(body.children.length, 1);
const row = body.children[0];
assert.equal(row.dataset.category, "duplicate");
assert.equal(row.children[0].textContent, "safe&name.xml");
assert.match(row.children[2].children[0].textContent, /03\/11\/2026 12:43:00 UTC/);
assert.equal(row.children[2].children[1].children[0].textContent, "Altri esiti nello stesso file (1)");
assert.equal(list.refreshed, true);
console.log("OK: live rendering, real import date, one file row and expandable bodies.");
