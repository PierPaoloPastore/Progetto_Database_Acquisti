document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("import-form");
    const fileInput = document.getElementById("files");
    const submitBtn = document.getElementById("import-submit-btn");
    const progressBox = document.getElementById("import-progress");
    const progressText = document.getElementById("import-progress-text");
    const progressCount = document.getElementById("import-progress-count");
    const progressBar = document.getElementById("import-progress-bar");
    const summaryCard = document.getElementById("import-summary-live");
    const summaryServer = document.getElementById("import-summary-server");
    const summaryTotal = document.getElementById("import-summary-total");
    const summaryImported = document.getElementById("import-summary-imported");
    const summarySkipped = document.getElementById("import-summary-skipped");
    const summaryErrors = document.getElementById("import-summary-errors");
    const summaryErrorsList = document.getElementById("import-summary-errors-list");
    const summaryErrorsBody = document.getElementById("import-summary-errors-body");

    if (!form || !fileInput) {
        return;
    }

    const MAX_BATCH_BYTES = 8 * 1024 * 1024;
    const MAX_BATCH_FILES = 200;
    const SERVER_LIMIT_BYTES = 16 * 1024 * 1024;
    const ERROR_LIST_LIMIT = 50;

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
        fileInput.disabled = disabled;
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
        if (summaryErrorsList) {
            summaryErrorsList.classList.add("d-none");
        }
        if (summaryErrorsBody) {
            summaryErrorsBody.innerHTML = "";
        }
    };

    const renderSummary = (summary, errorDetails) => {
        if (!summaryCard) {
            return;
        }
        summaryCard.classList.remove("d-none");
        if (summaryTotal) summaryTotal.textContent = summary.total_files;
        if (summaryImported) summaryImported.textContent = summary.imported;
        if (summarySkipped) summarySkipped.textContent = summary.skipped;
        if (summaryErrors) summaryErrors.textContent = summary.errors;

        if (summaryErrorsList && summaryErrorsBody) {
            if (errorDetails.length > 0) {
                summaryErrorsList.classList.remove("d-none");
                summaryErrorsBody.innerHTML = "";
                errorDetails.slice(0, ERROR_LIST_LIMIT).forEach((item) => {
                    const row = document.createElement("tr");
                    const fileCell = document.createElement("td");
                    const msgCell = document.createElement("td");
                    fileCell.textContent = item.file_name || "-";
                    msgCell.textContent = item.message || "Errore";
                    row.appendChild(fileCell);
                    row.appendChild(msgCell);
                    summaryErrorsBody.appendChild(row);
                });
                if (errorDetails.length > ERROR_LIST_LIMIT) {
                    const row = document.createElement("tr");
                    const cell = document.createElement("td");
                    cell.colSpan = 2;
                    cell.className = "text-muted";
                    cell.textContent = `Mostrati i primi ${ERROR_LIST_LIMIT} errori.`;
                    row.appendChild(cell);
                    summaryErrorsBody.appendChild(row);
                }
            } else {
                summaryErrorsList.classList.add("d-none");
            }
        }
    };

    const uploadBatch = async (batch) => {
        const formData = new FormData();
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
        const files = Array.from(fileInput.files || []);
        if (files.length === 0) {
            return;
        }

        const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
        const tooLarge = files.filter((file) => file.size > SERVER_LIMIT_BYTES);
        if (tooLarge.length > 0) {
            alert(`Alcuni file superano il limite di ${Math.round(SERVER_LIMIT_BYTES / (1024 * 1024))}MB.`);
            return;
        }

        const batches = buildBatches(files);
        const needsBatching = batches.length > 1 || totalBytes > MAX_BATCH_BYTES || files.length > MAX_BATCH_FILES;
        if (!needsBatching) {
            return;
        }

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

        const aggregate = {
            total_files: 0,
            imported: 0,
            skipped: 0,
            errors: 0,
            details: [],
        };

        try {
            for (let index = 0; index < batches.length; index += 1) {
                const batch = batches[index];
                updateProgress(index + 1, batches.length, batch.length);
                const data = await uploadBatch(batch);

                aggregate.total_files += data.total_files || batch.length;
                aggregate.imported += data.imported || 0;
                aggregate.skipped += data.skipped || 0;
                aggregate.errors += data.errors || 0;
                if (Array.isArray(data.details)) {
                    aggregate.details = aggregate.details.concat(data.details);
                }
            }

            updateProgress(batches.length, batches.length, 0);
            renderSummary(
                aggregate,
                aggregate.details.filter((item) => item.status === "error")
            );
        } catch (error) {
            showError("Errore durante l'import batch.");
        } finally {
            toggleDisabled(false);
        }
    });
});
