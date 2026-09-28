// Run: node tests/test_import_progress.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("app/static/js/import_batch.js", "utf8");
const code = source.slice(source.indexOf("    const startLiveProgress ="), source.indexOf("    const uploadBatch ="));

(async () => {
    let now = 0;
    let fail = false;
    let pending;
    let calls = 0;
    const timers = new Map();
    let id = 0;
    const status = { remove() { this.removed = true; } };
    const bar = { style: {}, setAttribute() {} };
    const context = {
        document: { createElement: () => status },
        progressBox: { appendChild() {} }, progressBar: bar,
        form: { action: "http://localhost/import/run" },
        window: { location: { href: "http://localhost/import/run" } },
        URL, AbortController, Date: { now: () => now },
        setTimeout: (fn, delay) => { timers.set(++id, { fn, delay }); return id; },
        clearTimeout: key => timers.delete(key),
        fetch: async (url, options) => {
            calls++;
            assert.equal(url.pathname, "/import/status/test-id");
            assert.equal(options.cache, "no-store");
            if (pending) await pending;
            if (fail) throw Error("offline");
            return { ok: true, json: async () => ({ total_files: 3, reconcile: 1,
                details: [{ status: "reconcile", file_name: "invoice.xml", stage: "started" }] }) };
        },
    };
    vm.createContext(context);
    vm.runInContext(code + "\nglobalThis.start = startLiveProgress;", context);
    const tick = async () => {
        const [key, timer] = [...timers].find(([, value]) => value.delay !== 10000);
        timers.delete(key);
        await timer.fn();
    };
    let stop = context.start("test-id", 10);
    await tick();
    assert.match(status.textContent, /2 di 10/);
    assert.match(status.textContent, /invoice.xml/);
    assert.equal(bar.style.width, "20%");
    now = 65000;
    await tick();
    assert.match(status.textContent, /Nessun nuovo avanzamento/);
    fail = true;
    await tick();
    assert.match(status.textContent, /potrebbe continuare/);
    stop();
    assert.equal(timers.size, 0);
    assert.equal(status.removed, true);
    fail = false;
    stop = context.start("test-id");
    await tick();
    assert.match(status.textContent, /^2 file/);
    let release;
    pending = new Promise(resolve => { release = resolve; });
    const running = tick();
    stop();
    const previousText = status.textContent;
    release();
    await running;
    assert.equal(status.textContent, previousText);
    assert.equal(timers.size, 0);
    assert.equal(calls, 5);
    console.log("OK: progress, stalled update, network failure, unknown total, cleanup and late response.");
})().catch(error => { console.error(error); process.exitCode = 1; });
