document.addEventListener("DOMContentLoaded", () => {
    setupTabSwitching();
    setupInvoiceFilter();
    setupPdfPreview();
    setupPaymentsSplitter();
    setupPaymentOcr();
    applyPresetPayment();
});

function setupTabSwitching() {
    const tabButtons = document.querySelectorAll("[data-tab-target]");
    const sections = document.querySelectorAll(".tab-section");
    const params = new URLSearchParams(window.location.search);
    const forcedTab = params.get("tab");
    const presetDocId = params.get("document_id");
    const presetDocIds = params.get("document_ids");

    const activateTab = (targetId) => {
        let found = false;

        tabButtons.forEach((btn) => {
            const isTarget = btn.getAttribute("data-tab-target") === targetId;
            btn.classList.toggle("active", isTarget);
            if (isTarget) found = true;
        });

        sections.forEach((section) => {
            section.classList.toggle("d-none", section.id !== targetId);
        });

        if (found) {
            history.replaceState(null, "", `#${targetId}`);
        }
    };

    tabButtons.forEach((btn) => {
        btn.addEventListener("click", (event) => {
            event.preventDefault();
            const target = btn.getAttribute("data-tab-target");

            activateTab(target);
        });
    });

    const initialHash = window.location.hash ? window.location.hash.replace("#", "") : "";
    const defaultTarget =
        ((presetDocId || presetDocIds) ? "tab-new" : "") ||
        forcedTab ||
        initialHash ||
        document.querySelector("[data-tab-target].active")?.getAttribute("data-tab-target") ||
        sections[0]?.id;

    if (defaultTarget) {
        activateTab(defaultTarget);
    }

    window.addEventListener("hashchange", () => {
        const target = window.location.hash ? window.location.hash.replace("#", "") : "";
        if (target) {
            activateTab(target);
        }
    });
}

function applyPresetPayment() {
    const params = new URLSearchParams(window.location.search);
    const docId = params.get("document_id");
    const docIdsRaw = params.get("document_ids");
    const docIds = docIdsRaw ? docIdsRaw.split(",").map((value) => value.trim()).filter(Boolean) : [];
    if (!docId && docIds.length === 0) return;

    const selectDoc = (targetDocId, withAmount) => {
        const checkbox = document.querySelector(`input[name="payment_id"][value="${targetDocId}"]`);
        const amountInput = document.querySelector(`input[name="amount_${targetDocId}"]`);

        if (checkbox) {
            checkbox.checked = true;
            const row = checkbox.closest(".invoice-row");
            if (row) {
                row.classList.add("border", "border-primary", "rounded");
                if (withAmount) {
                    row.scrollIntoView({ behavior: "smooth", block: "center" });
                }
            }
        }

        if (amountInput && withAmount) {
            amountInput.value = withAmount;
        }
    };

    const amount = params.get("amount");
    if (docId) {
        selectDoc(docId, amount);
    }

    if (docIds.length) {
        docIds.forEach((targetDocId, index) => {
            selectDoc(targetDocId, index === 0 ? null : null);
        });
        const firstRow = document.querySelector(`input[name="payment_id"][value="${docIds[0]}"]`)?.closest(".invoice-row");
        if (firstRow) {
            firstRow.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }
}

function setupInvoiceFilter() {
    const searchInput = document.getElementById("invoice-search");
    const dateInput = document.getElementById("invoice-date");
    const rows = document.querySelectorAll(".invoice-row");

    if (!searchInput && !dateInput) return;

    const applyFilter = () => {
        const query = (searchInput?.value || "").toLowerCase();
        const dateValue = (dateInput?.value || "").trim();

        rows.forEach((row) => {
            const text = (row.getAttribute("data-search") || row.textContent || "").toLowerCase();
            const matchText = !query || text.includes(query);
            const rowDate = row.getAttribute("data-date") || "";
            const matchDate = !dateValue || rowDate === dateValue;

            row.classList.toggle("d-none", !(matchText && matchDate));
        });
    };

    searchInput?.addEventListener("keyup", applyFilter);
    dateInput?.addEventListener("change", applyFilter);
    dateInput?.addEventListener("keyup", applyFilter);
}

function setupPdfPreview() {
    const fileInput = document.getElementById("pdf-file");
    const previewFrame = document.getElementById("pdf-preview");
    const placeholderDiv = document.getElementById("pdf-placeholder");

    if (!fileInput || !previewFrame || !placeholderDiv) {
        console.warn("PDF preview elements not found");
        return;
    }

    fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];

        // Validate file
        if (!file) {
            // No file selected - show placeholder
            previewFrame.removeAttribute("src");
            placeholderDiv.classList.remove("d-none");
            return;
        }

        // Validate file type
        if (file.type !== 'application/pdf') {
            alert('Solo file PDF sono consentiti.');
            fileInput.value = '';
            return;
        }

        // Validate file size (10MB limit)
        const maxSize = 10 * 1024 * 1024;
        if (file.size > maxSize) {
            alert('File troppo grande. Massimo 10MB consentito.');
            fileInput.value = '';
            return;
        }

        // Create blob URL and display
        const url = URL.createObjectURL(file);
        previewFrame.src = url;
        placeholderDiv.classList.add("d-none");

        // Clean up old blob URL when new file selected
        previewFrame.addEventListener('load', () => {
            URL.revokeObjectURL(url);
        }, { once: true });

        // Fallback if PDF blocked by browser
        setTimeout(() => {
            try {
                // Check if PDF loaded successfully
                const doc = previewFrame.contentDocument;
                if (!doc || doc.body.innerHTML === '') {
                    // Browser blocked PDF rendering
                    placeholderDiv.innerHTML = `
                        <p class="text-center text-muted">
                            <i class="bi bi-exclamation-triangle"></i><br>
                            Anteprima non disponibile nel browser.<br>
                            <a href="${url}" download="${file.name}" class="btn btn-sm btn-primary mt-2">
                                Scarica PDF
                            </a>
                        </p>
                    `;
                    placeholderDiv.classList.remove("d-none");
                }
            } catch (e) {
                // Cross-origin error (expected for blob URLs)
                // PDF likely loaded successfully
                console.debug('PDF preview loaded (cross-origin check blocked)');
            }
        }, 500);
    });
}

function setupPaymentsSplitter() {
    const split = document.querySelector(".split-container");
    const splitter = document.querySelector(".splitter");
    if (!split || !splitter) return;

    let dragging = false;
    let activePointerId = null;
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const updateWidth = (clientX) => {
        const rect = split.getBoundingClientRect();
        const rightWidth = rect.right - clientX;
        const pct = rightWidth / rect.width;
        const clamped = clamp(pct, 0.35, 0.7);
        split.style.setProperty("--payments-viewer-width", `${Math.round(clamped * 100)}%`);
    };

    splitter.addEventListener("pointerdown", (event) => {
        dragging = true;
        activePointerId = event.pointerId;
        document.body.classList.add("payments-resizing");
        splitter.setPointerCapture(event.pointerId);
        updateWidth(event.clientX);
        event.preventDefault();
    });

    splitter.addEventListener("pointermove", (event) => {
        if (!dragging || event.pointerId !== activePointerId) return;
        updateWidth(event.clientX);
    });

    const stopDragging = (event) => {
        if (!dragging || event.pointerId !== activePointerId) return;
        dragging = false;
        activePointerId = null;
        document.body.classList.remove("payments-resizing");
        splitter.releasePointerCapture(event.pointerId);
    };

    splitter.addEventListener("pointerup", stopDragging);
    splitter.addEventListener("pointercancel", stopDragging);
}

function setupPaymentOcr() {
    const button = document.getElementById("payment-ocr-btn");
    const status = document.getElementById("payment-ocr-status");
    const output = document.getElementById("payment-ocr-output");
    const fileInput = document.getElementById("pdf-file");
    const methodSelect = document.getElementById("payment_method");
    const notesInput = document.getElementById("notes");

    if (!button || !status || !output || !fileInput) {
        return;
    }

    const endpoint = button.getAttribute("data-ocr-endpoint");
    const mapEndpoint = button.getAttribute("data-ocr-map-endpoint") || endpoint;
    if (!endpoint) {
        return;
    }

    const setStatus = (message, isError = false) => {
        status.textContent = message || "";
        status.classList.toggle("text-danger", isError);
        status.classList.toggle("text-muted", !isError);
    };

    button.addEventListener("click", async () => {
        const file = fileInput.files[0];
        if (!file) {
            setStatus("Carica prima un PDF.", true);
            return;
        }

        button.disabled = true;
        setStatus("OCR in corso...", false);

        const payload = new FormData();
        payload.append("file", file);

        try {
            const response = await fetch(mapEndpoint, {
                method: "POST",
                body: payload,
            });
            const data = await response.json().catch(() => ({}));

            if (!response.ok || !data.success) {
                setStatus(data.error || "OCR fallito.", true);
                output.value = "";
                return;
            }

            output.value = data.text || "";
            applyPaymentMapping(data.fields || {}, methodSelect, notesInput);
            setStatus("OCR completato.", false);
        } catch (error) {
            setStatus("Errore di rete durante OCR.", true);
            output.value = "";
        } finally {
            button.disabled = false;
        }
    });
}

function applyPaymentMapping(fields, methodSelect, notesInput) {
    if (!fields || typeof fields !== "object") return;

    const badge = window.OcrBadge && window.OcrBadge.apply ? window.OcrBadge.apply : null;
    const docIdParam = new URLSearchParams(window.location.search).get("document_id");

    if (fields.payment_method && methodSelect) {
        const methodValue = fields.payment_method.value;
        if (methodValue) {
            methodSelect.value = methodValue;
            if (badge) badge(methodSelect, fields.payment_method.confidence || 0, "OCR");
        }
    }

    if (fields.notes && notesInput) {
        notesInput.value = fields.notes.value || "";
        if (badge) badge(notesInput, fields.notes.confidence || 0, "OCR");
    }

    if (fields.amount) {
        const amountValue = fields.amount.value;
        let targetDocId = docIdParam;

        if (!targetDocId) {
            const selected = document.querySelectorAll('input[name="payment_id"]:checked');
            if (selected.length === 1) {
                targetDocId = selected[0].value;
            }
        }

        if (targetDocId) {
            const amountInput = document.querySelector(`input[name="amount_${targetDocId}"]`);
            if (amountInput && amountValue) {
                amountInput.value = amountValue;
                if (badge) badge(amountInput, fields.amount.confidence || 0, "OCR");
            }
        }
    }
}
