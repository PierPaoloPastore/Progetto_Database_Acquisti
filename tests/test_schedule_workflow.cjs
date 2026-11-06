// Run: node tests/test_schedule_workflow.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("app/static/js/schedule.js", "utf8");

const element = () => ({
    disabled: false, checked: false, textContent: "", dataset: {},
    classList: { add() {}, remove() {} },
    addEventListener(event, handler) { this[event] = handler; },
});
const frame = element(), confirm = element(), checked = element(), error = element();
const cancel = element(), download = element(), count = element(), total = element(), id = element();
const previewDocuments = { replaceChildren(...children) { this.children = children; } };
const elements = {
    "[data-preview-frame]": frame, "[data-preview-confirm]": confirm,
    "[data-preview-download]": download, "[data-preview-count]": count,
    "[data-preview-total]": total, "[data-preview-id]": id,
    "[data-preview-documents]": previewDocuments, "[data-preview-pdf-details]": element(),
};
const modal = {
    querySelector: selector => elements[selector],
    getAttribute: name => ({ "data-confirm-url": "/confirm", "data-cancel-url": "/cancel", "data-preview-url": "/preview" })[name],
};
const printButton = { ...element(), innerHTML: "Genera estratto conto", getAttribute: () => "print" };
const idsInput = element(), form = { action: "/print" };
const row = { id: "1", getAttribute(name) { return name === "data-doc-id" ? this.id : "100"; } };
const selection = { checked: true, closest: () => row };
const requests = [];
let reloads = 0, visible = false, failConfirm = false, holdConfirm = null;
class FormData {
    constructor(sourceForm) { this.items = new Map(sourceForm ? [["document_ids", idsInput.value]] : []); }
    set(key, value) { this.items.set(key, value); }
}
const context = {
    previewModal: modal, previewFrame: frame, previewConfirm: confirm,
    previewChecked: checked, previewError: error, previewCancelButtons: [cancel],
    previewBusy: false, pendingPreview: null,
    schedulePrintInProgress: false, scheduleCbiInProgress: false,
    rowCheckboxes: [selection], bulkBar: element(), FormData,
    formatAmount: value => `${value.toFixed(2)} EUR`,
    document: {
        getElementById: name => name === "schedule-print-form" ? form : idsInput,
        createElement: () => ({ children: [], appendChild(child) { this.children.push(child); } }),
    },
    window: {
        location: { reload() { reloads++; } },
        URL: { createObjectURL: () => "blob:exact-generated-pdf", revokeObjectURL() {} },
        bootstrap: { Modal: { getOrCreateInstance: () => ({
            show() { visible = true; }, hide() { visible = false; },
        }) } },
    },
    alert: message => { throw Error(message); },
    fetch: async (url, options) => {
        requests.push({ url, body: Object.fromEntries(options.body.items) });
        if (url === "/print") return {
            ok: true,
            headers: { get: name => ({
                "content-type": "application/pdf", "X-Schedule-Token": "bound-to-generated-list",
                "X-Schedule-Count": "1", "X-Schedule-Total": "100.00", "X-Schedule-Id": "batch-test",
            })[name] || "" },
            blob: async () => "the-generated-pdf",
        };
        if (url === "/preview") return { ok: true, json: async () => ({ ok: true, documents: [{
            legal_entity_name: "Società prova", supplier_name: "Fornitore prova", document_number: "TEST-1", remaining_amount: "100.00",
        }] }) };
        if (url === "/confirm") {
            if (holdConfirm) await holdConfirm;
            if (failConfirm) throw Error("network unavailable");
        }
        return { ok: true, json: async () => ({ ok: true }) };
    },
};
vm.createContext(context);
const helperStart = source.indexOf("    const finishPreview =");
const helperEnd = source.indexOf("    rowCheckboxes.forEach((checkbox) => {", helperStart);
vm.runInContext(source.slice(helperStart, helperEnd), context);
const bulkStart = source.indexOf('    bulkBar?.addEventListener("click"');
const bulkEnd = source.indexOf("    sortHeaders.forEach", bulkStart);
vm.runInContext(source.slice(bulkStart, bulkEnd), context);
const generate = async () => {
    context.bulkBar.click({ target: { closest: () => printButton } });
    await new Promise(resolve => setImmediate(resolve));
};

(async () => {
    await generate();
    assert.equal(visible, true);
    assert.equal(reloads, 0);
    assert.deepEqual(requests.map(item => item.url), ["/print", "/preview"]);
    assert.equal(frame.src, download.href);
    assert.equal(count.textContent, "1");
    assert.equal(id.textContent, "batch-test");
    assert.equal(previewDocuments.children[0].children[2].textContent, "TEST-1");
    assert.equal(confirm.disabled, true);
    await confirm.click();
    assert.equal(requests.length, 2, "unchecked declaration cannot confirm");
    await cancel.click();
    assert.equal(visible, false);
    assert.equal(context.pendingPreview, null);
    assert.equal(requests.at(-1).url, "/cancel");
    assert.equal(reloads, 0);

    await generate();
    row.id = "3"; // La selezione cambia, ma la conferma usa solo il token del PDF.
    checked.checked = true;
    checked.change();
    failConfirm = true;
    await confirm.click();
    assert.match(error.textContent, /network unavailable/);
    assert.equal(reloads, 0);
    assert.ok(context.pendingPreview, "a failed request can be retried");
    failConfirm = false;
    let release;
    holdConfirm = new Promise(resolve => { release = resolve; });
    const finishing = confirm.click();
    const beforeDoubleClick = requests.length;
    await confirm.click();
    assert.equal(requests.length, beforeDoubleClick, "double clicks do not send another confirmation");
    release();
    await finishing;
    assert.equal(reloads, 1);
    assert.deepEqual(requests.at(-1).body, { token: "bound-to-generated-list" });
    assert.equal(requests.at(-1).url, "/confirm");
    console.log("OK: preview/download without programming, cancellation, explicit confirmation, frozen token, retry and double click.");
})().catch(error => { console.error(error); process.exitCode = 1; });
