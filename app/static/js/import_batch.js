document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("import-form");
    const fileInput = document.getElementById("files");
    const submitBtn = document.getElementById("import-submit-btn");
    const serverForm = document.getElementById("server-import-form");
    const serverBtn = document.getElementById("server-import-btn");
    const serverFolderInput = document.getElementById("server_folder");
    const progressBox = document.getElementById("import-progress");
    const progressText = document.getElementById("import-progress-text");
    const progressCount = document.getElementById("import-progress-count");
    const progressBar = document.getElementById("import-progress-bar");
    const summaryCard = document.getElementById("import-summary-live");
    const summaryServer = document.getElementById("import-summary-server");
    const summaryTotal = document.getElementById("import-summary-total");
    const summaryImported = document.getElementById("import-summary-imported");
    const summarySkipped = document.getElementById("import-summary-skipped");
    const summaryWarnings = document.getElementById("import-summary-warnings");
    const summaryErrors = document.getElementById("import-summary-errors");
    const summaryNarrative = document.getElementById("import-summary-narrative");
    const summaryReport = document.getElementById("import-summary-report");
    const summaryReportPath = document.getElementById("import-summary-report-path");
    const summaryReportLink = document.getElementById("import-summary-report-link");
    const summaryErrorsList = document.getElementById("import-summary-errors-list");
    const summaryErrorsBody = document.getElementById("import-summary-errors-body");
    let importSubmitting = false;

    if (!form || !fileInput) {
        return;
    }

    const MAX_BATCH_BYTES = 8 * 1024 * 1024;
    const MAX_BATCH_FILES = 200;
    const SERVER_LIMIT_BYTES = 16 * 1024 * 1024;

    const buildBatches = (files) => {
        const batches = [];
        let current = [];
        let currentBytes = 0;

        files.forEach((file) => {
            const exceedsBatch =
                current.length > 0 &&
                (currentBytes + file.size > MAX_BATCH_BYTES || current.length >= MAX_BATCH_FILES);

            if (exceedsBatch) {
                batches.push(current);
                current = [];
                currentBytes = 0;
            }

            current.push(file);
            currentBytes += file.size;
        });

        if (current.length > 0) {
            batches.push(current);
        }

        return batches;
    };

    const toggleDisabled = (disabled) => {
        if (submitBtn) {
            submitBtn.disabled = disabled;
        }
        if (serverBtn) {
            serverBtn.disabled = disabled;
        }
        if (serverFolderInput) {
            serverFolderInput.disabled = disabled;
        }
        fileInput.disabled = disabled;
    };

    const lockSubmitButton = (button, message) => {
        if (button) {
            button.disabled = true;
            button.dataset.originalHtml = button.innerHTML;
            button.innerHTML = `<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> ${message}`;
        }
    };

    const unlockSubmitButton = (button) => {
        if (!button) return;
        button.disabled = false;
        if (button.dataset.originalHtml) {
            button.innerHTML = button.dataset.originalHtml;
        }
    };

    const updateProgress = (index, total, count) => {
        if (!progressBox || !progressBar || !progressText) {
            return;
        }
        progressBox.classList.remove("d-none");
        const pct = total > 0 ? Math.round((index / total) * 100) : 0;
        progressBar.style.width = `${pct}%`;
        progressText.textContent = `Batch ${index} di ${total}`;
        if (progressCount) {
            progressCount.textContent = `${count} file`;
        }
    };

    const startBusyProgress = (message) => {
        if (!progressBox || !progressBar || !progressText) {
            return;
        }
        progressBox.classList.remove("d-none");
        progressText.textContent = message;
        progressBar.style.width = "100%";
        progressBar.classList.add("progress-bar-striped", "progress-bar-animated");
        if (progressCount) {
            progressCount.textContent = "In corso...";
        }
    };

    const stopBusyProgress = (message) => {
        if (!progressBox || !progressBar || !progressText) {
            return;
        }
        progressText.textContent = message;
        progressBar.classList.remove("progress-bar-striped", "progress-bar-animated");
        if (progressCount) {
            progressCount.textContent = "";
        }
    };

    const showError = (message) => {
        if (progressText) {
            progressText.textContent = message;
        }
        if (progressBar) {
            progressBar.classList.add("bg-danger");
        }
    };

    const resetSummary = () => {
        if (summaryCard) {
            summaryCard.classList.add("d-none");
        }
        if (summaryReport) {
            summaryReport.classList.add("d-none");
        }
        if (summaryReportPath) {
            summaryReportPath.textContent = "";
        }
        if (summaryReportLink) {
            summaryReportLink.classList.add("d-none");
            summaryReportLink.removeAttribute("href");
        }
        if (summaryErrorsList) {
            summaryErrorsList.classList.add("d-none");
        }
        if (summaryErrorsBody) {
            summaryErrorsBody.innerHTML = "";
        }
        if (summaryNarrative) {
            summaryNarrative.classList.add("d-none");
            summaryNarrative.textContent = "";
        }
    };

    const buildNarrative = (summary) => {
        if (summary.narrative) return summary.narrative;
        const total = Number(summary.total_files || 0);
        const imported = Number(summary.imported || 0);
        const skipped = Number(summary.skipped || 0);
        const warnings = Number(summary.warnings || 0);
        const errors = Number(summary.errors || 0);
        if (!total) return "Non ho trovato file XML o P7M da importare.";
        if (imported === 0 && skipped > 0 && errors === 0 && warnings === 0) {
            return `Ho letto ${total} file, ma non ho inserito nuovi documenti: risultano gia presenti o duplicati.`;
        }
        if (imported === 0 && errors > 0) {
            return `Ho letto ${total} file, ma non ho inserito nuovi documenti. Ci sono ${errors} errori da controllare.`;
        }
        return `Ho letto ${total} file: ${imported} inseriti, ${skipped} saltati, ${warnings} warning, ${errors} errori.`;
    };

    const renderSummary = (summary, details) => {
        if (!summaryCard) {
            return;
        }
        summaryCard.classList.remove("d-none");
        if (summaryTotal) summaryTotal.textContent = summary.total_files;
        if (summaryImported) summaryImported.textContent = summary.imported;
        if (summarySkipped) summarySkipped.textContent = summary.skipped;
        if (summaryWarnings) summaryWarnings.textContent = summary.warnings || 0;
        if (summaryErrors) summaryErrors.textContent = summary.errors;
        if (summaryNarrative) {
            summaryNarrative.textContent = buildNarrative(summary);
            summaryNarrative.classList.remove("d-none");
        }
        if (summaryReport && summaryReportLink) {
            const baseUrl = summaryReportLink.getAttribute("data-report-url");
            const paths = summary.report_paths || (summary.report_path ? [summary.report_path] : []);
            summaryReport.querySelectorAll(".batch-report").forEach(link => link.remove());
            summaryReportLink.classList.add("d-none");
            if (summaryReportPath) summaryReportPath.textContent = "";
            paths.forEach((path, index) => {
                const link = document.createElement("a");
                const url = new URL(baseUrl, window.location.origin);
                url.searchParams.set("path", path);
                link.href = url.toString();
                link.textContent = `Report CSV ${index + 1} `;
                link.className = "batch-report ms-2";
                summaryReport.appendChild(link);
            });
            summaryReport.classList.toggle("d-none", paths.length === 0);
        }

        if (summaryErrorsList && summaryErrorsBody) {
            if (details.length > 0) {
                summaryErrorsList.classList.remove("d-none");
                summaryErrorsBody.innerHTML = "";
                details.forEach((item) => {
                    const row = document.createElement("tr");
                    const fileCell = document.createElement("td");
                    const statusCell = document.createElement("td");
                    const stageCell = document.createElement("td");
                    const msgCell = document.createElement("td");
                    fileCell.textContent = item.file_name || "-";
                    statusCell.textContent = item.status || "-";
                    stageCell.textContent = item.stage || "-";
                    msgCell.textContent = item.message || "Errore";
                    row.appendChild(fileCell);
                    const documentCell = document.createElement("td");
                    const existingCell = document.createElement("td");
                    documentCell.style.whiteSpace = "pre-line";
                    existingCell.style.whiteSpace = "pre-line";
                    documentCell.textContent = `${item.document_number || "-"} — ${item.document_date || "-"}\n${item.supplier_name || "-"}\nIntestazione: ${item.legal_entity_name || "-"}\n${item.document_data_source || "Dati non disponibili"}`;
                    existingCell.textContent = item.existing_file_name
                        ? `${item.existing_file_name}\n${item.existing_document_number || "-"} — ${item.existing_document_date || "-"}\nStesso nome file: ${item.same_file_name || "non verificato"}`
                        : "-";
                    if (item.document_url) {
                        const link = document.createElement("a");
                        link.href = item.document_url;
                        link.textContent = " Apri documento";
                        documentCell.appendChild(link);
                    }
                    row.appendChild(documentCell);
                    row.appendChild(existingCell);
                    row.appendChild(statusCell);
                    row.appendChild(stageCell);
                    row.appendChild(msgCell);
                    summaryErrorsBody.appendChild(row);
                });

            } else {
                summaryErrorsList.classList.add("d-none");
            }
        }
    };

    const recoveryLink = document.getElementById("import-last-batch");
    const rememberBatch = (batchId) => {
        const url = new URL(form.action || window.location.href, window.location.href);
        url.searchParams.set("batch_id", batchId);
        if (recoveryLink) {
            recoveryLink.href = url.toString();
            recoveryLink.classList.remove("d-none");
        }
        try { sessionStorage.setItem("last-import-batch", batchId); } catch (_) { /* Link resta disponibile. */ }
    };
    try {
        const lastBatch = sessionStorage.getItem("last-import-batch");
        if (lastBatch) rememberBatch(lastBatch);
    } catch (_) { /* Storage browser facoltativo. */ }
    const startBatch = () => {
        const bytes = crypto.getRandomValues(new Uint8Array(16));
        bytes[6] = (bytes[6] & 15) | 64;
        bytes[8] = (bytes[8] & 63) | 128;
        const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
        const id = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
        rememberBatch(id);
        return id;
    };

    const startLiveProgress = (batchId, totalFiles) => {
        const status = document.createElement("div");
        status.className = "small mt-2";
        progressBox.appendChild(status);
        const url = new URL(`status/${batchId}`, form.action || window.location.href);
        const started = Date.now();
        let changed = started;
        let signature = "";
        let stopped = false;
        let timer;
        let controller;
        status.textContent = "In attesa del primo aggiornamento dal server...";
        const poll = async () => {
            controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 10000);
            try {
                const response = await fetch(url, {
                    credentials: "same-origin", cache: "no-store", signal: controller.signal,
                    headers: { Accept: "application/json" },
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                if (stopped) return;
                const completed = Math.max(0, data.total_files - (data.reconcile || 0));
                const active = (data.details || []).find(item => item.status === "reconcile");
                const next = JSON.stringify([completed, active?.file_name, active?.stage]);
                if (next !== signature) { changed = Date.now(); signature = next; }
                const seconds = Math.floor((Date.now() - started) / 1000);
                const idle = Math.floor((Date.now() - changed) / 1000);
                status.textContent = `${completed}${totalFiles ? ` di ${totalFiles}` : ""} file con esito disponibile · ${seconds}s trascorsi.`
                    + (active ? ` In corso o da verificare: ${active.file_name}.` : "")
                    + (idle >= 60 ? ` Nessun nuovo avanzamento da ${idle}s; il server risponde. Attendi o consulta il riepilogo, senza rilanciare l'importazione.` : "");
                if (totalFiles) {
                    const percent = Math.min(100, Math.round(completed / totalFiles * 100));
                    progressBar.style.width = `${percent}%`;
                    progressBar.setAttribute("aria-valuenow", percent);
                }
            } catch (_) {
                if (!stopped) status.textContent = "Aggiornamento non disponibile: l'importazione potrebbe continuare. Nuovo controllo tra 5 secondi; non rilanciarla.";
            } finally {
                clearTimeout(timeout);
                if (!stopped) timer = setTimeout(poll, 5000);
            }
        };
        timer = setTimeout(poll, 1000);
        return () => {
            stopped = true;
            clearTimeout(timer);
            controller?.abort();
            status.remove();
        };
    };

    const uploadBatch = async (batch, batchId) => {
        const formData = new FormData();
        formData.append("batch_id", batchId);
        batch.forEach((file) => {
            const name = file.webkitRelativePath || file.name;
            formData.append("files", file, name);
        });

        const response = await fetch(form.action, {
            method: "POST",
            body: formData,
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                Accept: "application/json",
            },
            credentials: "same-origin",
        });

        if (!response.ok) {
            throw new Error(`Errore HTTP ${response.status}`);
        }

        return response.json();
    };

    form.addEventListener("submit", async (event) => {
        if (importSubmitting) {
            event.preventDefault();
            return;
        }
        importSubmitting = true;
        lockSubmitButton(submitBtn, "Importazione...");

        const files = Array.from(fileInput.files || []);
        if (files.length === 0) {
            importSubmitting = false;
            unlockSubmitButton(submitBtn);
            return;
        }

        const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
        const tooLarge = files.filter((file) => file.size > SERVER_LIMIT_BYTES);
        if (tooLarge.length > 0) {
            alert(`Alcuni file superano il limite di ${Math.round(SERVER_LIMIT_BYTES / (1024 * 1024))}MB.`);
            importSubmitting = false;
            unlockSubmitButton(submitBtn);
            return;
        }

        const batches = buildBatches(files);

        event.preventDefault();
        toggleDisabled(true);
        resetSummary();
        if (summaryServer) {
            summaryServer.classList.add("d-none");
        }
        if (progressBox) {
            progressBox.classList.remove("d-none");
        }
        if (progressBar) {
            progressBar.classList.remove("bg-danger");
        }

        const batchId = startBatch();
        const stopLiveProgress = startLiveProgress(batchId, files.length);
        const aggregate = {
            total_files: 0,
            imported: 0,
            skipped: 0,
            warnings: 0,
            errors: 0,
            details: [],
            report_paths: [],
        };

        try {
            for (let index = 0; index < batches.length; index += 1) {
                const batch = batches[index];
                updateProgress(index, batches.length, aggregate.total_files);
                progressText.textContent = `Elaborazione gruppo ${index + 1} di ${batches.length}...`;
                const data = await uploadBatch(batch, batchId);

                aggregate.total_files += data.total_files || batch.length;
                aggregate.imported += data.imported || 0;
                aggregate.skipped += data.skipped || 0;
                aggregate.warnings += data.warnings || 0;
                aggregate.errors += data.errors || 0;
                if (data.report_path) aggregate.report_paths.push(data.report_path);
                if (Array.isArray(data.details)) {
                    aggregate.details = aggregate.details.concat(data.details);
                }
            }

            updateProgress(batches.length, batches.length, 0);
            renderSummary(aggregate, aggregate.details || []);
        } catch (error) {
            renderSummary(aggregate, aggregate.details || []);
            showError(`Risposta interrotta: il batch ${batchId} potrebbe essere già registrato. Controlla il riepilogo prima di riprovare.`);
        } finally {
            stopLiveProgress();
            importSubmitting = false;
            toggleDisabled(false);
            unlockSubmitButton(submitBtn);
        }
    });

    if (serverForm) {
        serverForm.addEventListener("submit", async (event) => {
            if (importSubmitting) {
                event.preventDefault();
                return;
            }
            if (serverFolderInput && !serverFolderInput.value.trim()) {
                event.preventDefault();
                alert("Inserisci un percorso server valido.");
                return;
            }
            event.preventDefault();
            importSubmitting = true;
            const serverData = new FormData(serverForm);
            toggleDisabled(true);
            lockSubmitButton(serverBtn, "Importazione...");
            const batchId = startBatch();
            serverData.append("batch_id", batchId);
            resetSummary();
            if (summaryServer) {
                summaryServer.classList.add("d-none");
            }
            if (progressBar) {
                progressBar.classList.remove("bg-danger");
            }
            startBusyProgress("Import cartella server in corso...");
            const stopLiveProgress = startLiveProgress(batchId);

            try {
                const targetUrl = serverForm.getAttribute("action") || window.location.href;
                const response = await fetch(targetUrl, {
                    method: "POST",
                    body: serverData,
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        Accept: "application/json",
                    },
                    credentials: "same-origin",
                });
                if (!response.ok) {
                    throw new Error(`Errore HTTP ${response.status}`);
                }
                const data = await response.json();
                stopBusyProgress("Import cartella server completato.");
                renderSummary(data, data.details || []);
            } catch (error) {
                showError("Risposta interrotta: alcuni documenti potrebbero essere registrati. Ricarica il riepilogo prima di riprovare.");
            } finally {
                stopLiveProgress();
                progressBar?.classList.remove("progress-bar-striped", "progress-bar-animated");
                importSubmitting = false;
                toggleDisabled(false);
                unlockSubmitButton(serverBtn);
            }
        });
    }
});
