document.addEventListener("DOMContentLoaded", () => {
    setupTabSwitching();
    setupInvoiceFilter();
    setupPaymentAmountAutofill();
    setupPaymentSelectionUX();
    setupPdfPreview();
    setupPaymentsSplitter();
    setupPaymentOcr();
    setupPaymentDateDefault();
    applyPresetPayment();
});

const refreshSelect2 = (select) => {
    if (!select || !window.jQuery) return;
    const $el = window.jQuery(select);
    if ($el.data("select2")) {
        $el.trigger("change.select2");
    }
};

const normalizeSearchText = (value) => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();

const compactSearchText = (value) => normalizeSearchText(value).replace(/\s+/g, "");

const matchesSearchText = (haystack, query) => {
    const normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) return true;

    const normalizedHaystack = normalizeSearchText(haystack);
    if (normalizedHaystack.includes(normalizedQuery)) {
        return true;
    }

    return compactSearchText(normalizedHaystack).includes(compactSearchText(normalizedQuery));
};

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

        const targetSection = document.getElementById(targetId);
        if (window.initSelect2Controls && targetSection) {
            window.initSelect2Controls(targetSection);
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
            checkbox.dispatchEvent(new Event("change", { bubbles: true }));
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
            amountInput.dispatchEvent(new Event("input", { bubbles: true }));
            amountInput.dispatchEvent(new Event("change", { bubbles: true }));
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
    const chip = document.getElementById("invoice-entity-chip");
    const chipLabel = document.getElementById("invoice-entity-chip-label");
    const chipRemove = document.getElementById("invoice-entity-chip-remove");
    const ibanSelect = document.getElementById("bank-account-iban");
    const ibanEmptyOption = document.getElementById("bank-account-empty");
    let activeEntityId = null;

    if (!searchInput && !dateInput) return;

    const applyFilter = () => {
        const query = searchInput?.value || "";
        const dateValue = (dateInput?.value || "").trim();

        rows.forEach((row) => {
            const text = row.getAttribute("data-search") || row.textContent || "";
            const matchText = matchesSearchText(text, query);
            const rowDate = row.getAttribute("data-date") || "";
            const matchDate = !dateValue || rowDate === dateValue;
            const rowEntity = row.getAttribute("data-legal-entity-id") || "";
            const matchEntity = !activeEntityId || rowEntity === activeEntityId;

            row.classList.toggle("d-none", !(matchText && matchDate && matchEntity));
        });
    };

    const updateBankAccounts = (entityId) => {
        if (!ibanSelect) return;
        const options = Array.from(ibanSelect.querySelectorAll("option")).filter(
            (option) => option.value
        );
        let visibleCount = 0;
        options.forEach((option) => {
            const optionEntityId = option.getAttribute("data-legal-entity-id") || "";
            const shouldShow = !entityId || optionEntityId === entityId;
            option.hidden = !shouldShow;
            option.disabled = !shouldShow;
            if (shouldShow) {
                visibleCount += 1;
            }
        });

        if (ibanEmptyOption) {
            const showEmpty = entityId && visibleCount === 0;
            ibanEmptyOption.hidden = !showEmpty;
            ibanEmptyOption.disabled = !showEmpty;
        }

        if (ibanSelect.value) {
            const selected = options.find((option) => option.value === ibanSelect.value);
            if (selected && selected.classList.contains("d-none")) {
                ibanSelect.value = "";
            }
        }
        refreshSelect2(ibanSelect);
    };

    const setEntityFilter = (entityId, entityName) => {
        if (!entityId) return;
        activeEntityId = String(entityId);
        if (chip && chipLabel) {
            chipLabel.textContent = entityName ? `Intestatario: ${entityName}` : "Intestatario";
            chip.classList.remove("d-none");
        }
        updateBankAccounts(activeEntityId);
        applyFilter();
    };

    const clearEntityFilter = () => {
        activeEntityId = null;
        if (chip) {
            chip.classList.add("d-none");
        }
        updateBankAccounts(null);
        applyFilter();
    };

    chipRemove?.addEventListener("click", (event) => {
        event.preventDefault();
        clearEntityFilter();
    });

    rows.forEach((row) => {
        const checkbox = row.querySelector('input[name="payment_id"]');
        if (!checkbox) return;
        checkbox.addEventListener("change", () => {
            if (!checkbox.checked || activeEntityId) return;
            const entityId = row.getAttribute("data-legal-entity-id") || "";
            const entityName = row.getAttribute("data-legal-entity-name") || "";
            setEntityFilter(entityId, entityName);
        });
    });

    const preselected = document.querySelector('input[name="payment_id"]:checked');
    if (preselected) {
        const row = preselected.closest(".invoice-row");
        if (row) {
            const entityId = row.getAttribute("data-legal-entity-id") || "";
            const entityName = row.getAttribute("data-legal-entity-name") || "";
            setEntityFilter(entityId, entityName);
        }
    }
    updateBankAccounts(activeEntityId);

    searchInput?.addEventListener("input", applyFilter);
    dateInput?.addEventListener("change", applyFilter);
    dateInput?.addEventListener("keyup", applyFilter);
}

function setupPaymentAmountAutofill() {
    const checkboxes = document.querySelectorAll('input[name="payment_id"]');
    if (!checkboxes.length) return;

    checkboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            if (!checkbox.checked) return;
            const row = checkbox.closest(".invoice-row");
            if (!row) return;
            const due = row.getAttribute("data-due");
            if (!due) return;

            const amountInput =
                row.querySelector(`input[name="amount_${checkbox.value}"]`) ||
                row.querySelector('input[name^="amount_"]');
            if (!amountInput) return;

            amountInput.value = due;
        });
    });
}

function setupPaymentSelectionUX() {
    const form = document.querySelector('#tab-new form[action]');
    const invoiceBody = document.querySelector(".invoice-body");
    const rows = Array.from(document.querySelectorAll(".invoice-row"));
    const summaryCount = document.getElementById("payment-selected-count");
    const summaryTotal = document.getElementById("payment-selected-total");
    const summarySuppliers = document.getElementById("payment-selected-suppliers");
    const modalEl = document.getElementById("payment-confirm-modal");
    const confirmSubmitButton = document.getElementById("payment-confirm-submit");
    const confirmCount = document.getElementById("payment-confirm-count");
    const confirmSupplierCount = document.getElementById("payment-confirm-supplier-count");
    const confirmTotal = document.getElementById("payment-confirm-total");
    const confirmGroups = document.getElementById("payment-confirm-groups");

    if (!form || !invoiceBody || !rows.length) return;

    let selectionSequence = 0;
    let bypassConfirmation = false;
    const confirmModal = modalEl && window.bootstrap?.Modal ? new window.bootstrap.Modal(modalEl) : null;

    const escapeHtml = (value) => String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");

    const formatCurrency = (value) => {
        const amount = Number(value || 0);
        if (Number.isNaN(amount)) return "0,00 €";
        return amount.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
    };

    const getCheckbox = (row) => row.querySelector('input[name="payment_id"]');

    const getAmountInput = (row, checkbox) => {
        const targetCheckbox = checkbox || getCheckbox(row);
        if (!targetCheckbox) return null;
        return row.querySelector(`input[name="amount_${targetCheckbox.value}"]`);
    };

    const getRowAmount = (row, checkbox) => {
        const amountInput = getAmountInput(row, checkbox);
        const rawValue = (amountInput?.value || "0").replace(",", ".");
        const amount = Number(rawValue);
        return Number.isNaN(amount) ? 0 : amount;
    };

    const getSelectedRows = () => rows.filter((row) => getCheckbox(row)?.checked);

    const updateSelectionSummary = () => {
        const selectedRows = getSelectedRows();
        const total = selectedRows.reduce((sum, row) => sum + getRowAmount(row), 0);
        const supplierNames = Array.from(new Set(
            selectedRows
                .map((row) => (row.getAttribute("data-supplier-name") || "").trim())
                .filter(Boolean)
        ));

        if (summaryCount) summaryCount.textContent = selectedRows.length.toString();
        if (summaryTotal) summaryTotal.innerHTML = `${formatCurrency(total)}`;
        if (summarySuppliers) {
            if (!supplierNames.length) {
                summarySuppliers.textContent = "Nessun fornitore selezionato";
            } else if (supplierNames.length === 1) {
                summarySuppliers.textContent = supplierNames[0];
            } else {
                summarySuppliers.textContent = `${supplierNames.length} fornitori selezionati`;
            }
        }
    };

    const reorderRows = () => {
        const orderedRows = [...rows].sort((leftRow, rightRow) => {
            const leftChecked = Boolean(getCheckbox(leftRow)?.checked);
            const rightChecked = Boolean(getCheckbox(rightRow)?.checked);
            if (leftChecked !== rightChecked) {
                return leftChecked ? -1 : 1;
            }
            if (leftChecked && rightChecked) {
                return Number(rightRow.dataset.selectedOrder || "0") - Number(leftRow.dataset.selectedOrder || "0");
            }
            return Number(leftRow.dataset.originalOrder || "0") - Number(rightRow.dataset.originalOrder || "0");
        });

        orderedRows.forEach((row) => invoiceBody.appendChild(row));
    };

    const buildSelectionItems = () => getSelectedRows().map((row) => {
        const checkbox = getCheckbox(row);
        const amount = getRowAmount(row, checkbox);
        return {
            documentId: row.getAttribute("data-document-id") || checkbox?.value || "",
            documentLabel: row.getAttribute("data-document-label") || `Documento #${checkbox?.value || ""}`,
            supplierName: row.getAttribute("data-supplier-name") || "Fornitore non disponibile",
            legalEntityName: row.getAttribute("data-legal-entity-name") || "",
            amount,
        };
    });

    const renderConfirmation = () => {
        const items = buildSelectionItems();
        const groupedBySupplier = new Map();

        items.forEach((item) => {
            const key = `${item.supplierName || "Fornitore non disponibile"}|${item.legalEntityName || ""}`;
            if (!groupedBySupplier.has(key)) {
                groupedBySupplier.set(key, {
                    supplierName: item.supplierName || "Fornitore non disponibile",
                    legalEntityName: item.legalEntityName || "",
                    total: 0,
                    count: 0,
                    items: [],
                });
            }
            const group = groupedBySupplier.get(key);
            group.total += item.amount;
            group.count += 1;
            group.items.push(item);
        });

        const total = items.reduce((sum, item) => sum + item.amount, 0);

        if (confirmCount) confirmCount.textContent = items.length.toString();
        if (confirmSupplierCount) confirmSupplierCount.textContent = groupedBySupplier.size.toString();
        if (confirmTotal) confirmTotal.innerHTML = `${formatCurrency(total)}`;

        if (confirmGroups) {
            confirmGroups.innerHTML = Array.from(groupedBySupplier.values()).map((group) => `
                <details class="payment-confirm-item payment-confirm-group">
                    <summary class="payment-confirm-item-header payment-confirm-toggle">
                        <div>
                            <div class="payment-confirm-item-title">${escapeHtml(group.supplierName)}</div>
                            <div class="payment-confirm-item-meta">${escapeHtml(group.legalEntityName || "Intestatario non indicato")}</div>
                            <div class="payment-confirm-item-meta">${escapeHtml(`${group.count} documenti`)}</div>
                        </div>
                        <div class="payment-confirm-item-header-right">
                            <div class="payment-confirm-item-amount">${escapeHtml(formatCurrency(group.total))}</div>
                            <div class="payment-confirm-toggle-hint">Dettaglio</div>
                        </div>
                    </summary>
                    <div class="payment-confirm-subitems">
                        ${group.items.map((item) => `
                            <div class="payment-confirm-subitem">
                                <span class="payment-confirm-subitem-label">${escapeHtml(item.documentLabel)}</span>
                                <span class="payment-confirm-subitem-amount">${escapeHtml(formatCurrency(item.amount))}</span>
                            </div>
                        `).join("")}
                    </div>
                </details>
            `).join("");
        }
    };

    rows.forEach((row, index) => {
        row.dataset.originalOrder = String(index);
        const checkbox = getCheckbox(row);
        const amountInput = getAmountInput(row, checkbox);
        if (checkbox?.checked) {
            selectionSequence += 1;
            row.dataset.selectedOrder = String(selectionSequence);
            row.classList.add("invoice-row-selected");
        }

        checkbox?.addEventListener("change", () => {
            if (checkbox.checked) {
                selectionSequence += 1;
                row.dataset.selectedOrder = String(selectionSequence);
            } else {
                row.dataset.selectedOrder = "0";
            }
            row.classList.toggle("invoice-row-selected", checkbox.checked);
            reorderRows();
            updateSelectionSummary();
        });

        amountInput?.addEventListener("input", updateSelectionSummary);
        amountInput?.addEventListener("change", updateSelectionSummary);
    });

    invoiceBody.addEventListener("click", (event) => {
        const target = event.target;
        const row = target.closest(".invoice-row");
        if (!row) return;
        if (target.closest("a, button, input, label, select, textarea")) return;
        const checkbox = getCheckbox(row);
        if (!checkbox || checkbox.disabled) return;
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    });

    form.addEventListener("submit", (event) => {
        if (bypassConfirmation) {
            bypassConfirmation = false;
            return;
        }

        if (!confirmModal) {
            return;
        }

        const selectedRows = getSelectedRows();
        if (!selectedRows.length) {
            return;
        }

        event.preventDefault();
        renderConfirmation();
        confirmModal.show();
    });

    confirmSubmitButton?.addEventListener("click", () => {
        bypassConfirmation = true;
        confirmModal?.hide();
        form.requestSubmit();
    });

    reorderRows();
    updateSelectionSummary();
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

function setupPaymentDateDefault() {
    const input = document.getElementById("payment-date");
    if (!input || input.value) return;
    const today = new Date();
    const pad = (value) => String(value).padStart(2, "0");
    input.value = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
}

function applyPaymentMapping(fields, methodSelect, notesInput) {
    if (!fields || typeof fields !== "object") return;

    const badge = window.OcrBadge && window.OcrBadge.apply ? window.OcrBadge.apply : null;
    const docIdParam = new URLSearchParams(window.location.search).get("document_id");
    const dateInput = document.getElementById("payment-date");

    if (fields.payment_method && methodSelect) {
        const methodValue = fields.payment_method.value;
        if (methodValue) {
            methodSelect.value = methodValue;
            if (badge) badge(methodSelect, fields.payment_method.confidence || 0, "OCR");
            refreshSelect2(methodSelect);
        }
    }

    if (fields.notes && notesInput) {
        notesInput.value = fields.notes.value || "";
        if (badge) badge(notesInput, fields.notes.confidence || 0, "OCR");
    }

    if (fields.payment_date && dateInput) {
        const dateValue = fields.payment_date.value;
        if (dateValue) {
            dateInput.value = dateValue;
            if (badge) badge(dateInput, fields.payment_date.confidence || 0, "OCR");
        }
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
                amountInput.dispatchEvent(new Event("input", { bubbles: true }));
                amountInput.dispatchEvent(new Event("change", { bubbles: true }));
                if (badge) badge(amountInput, fields.amount.confidence || 0, "OCR");
            }
        }
    }
}
