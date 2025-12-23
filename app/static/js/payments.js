document.addEventListener("DOMContentLoaded", () => {
    setupTabSwitching();
    setupInvoiceFilter();
    setupPdfPreview();
    setupPaymentOcr();
});

function setupTabSwitching() {
    const tabButtons = document.querySelectorAll("[data-tab-target]");
    const sections = document.querySelectorAll(".tab-section");

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

function setupPaymentOcr() {
    const button = document.getElementById("payment-ocr-btn");
    const status = document.getElementById("payment-ocr-status");
    const output = document.getElementById("payment-ocr-output");
    const fileInput = document.getElementById("pdf-file");

    if (!button || !status || !output || !fileInput) {
        return;
    }

    const endpoint = button.getAttribute("data-ocr-endpoint");
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
            const response = await fetch(endpoint, {
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
            setStatus("OCR completato.", false);
        } catch (error) {
            setStatus("Errore di rete durante OCR.", true);
            output.value = "";
        } finally {
            button.disabled = false;
        }
    });
}
