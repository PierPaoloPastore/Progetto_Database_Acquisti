const paymentUiState = {
    selections: new Map(),
    selectionSequence: 0,
    activeEntityId: null,
    activeEntityName: "",
    bypassConfirmation: false,
    confirmModal: null,
    invoiceFetchController: null,
    invoiceLoading: false,
};

document.addEventListener("DOMContentLoaded", () => {
    setupTabSwitching();
    setupPaymentsWorkspace();
    setupPdfPreview();
    setupPaymentsSplitter();
    setupPaymentOcr();
    setupPaymentDateDefault();
});

const refreshSelect2 = (select) => {
    if (!select || !window.jQuery) return;
    const $el = window.jQuery(select);
    if ($el.data("select2")) {
        $el.trigger("change.select2");
    }
};

const formatCurrency = (value) => {
    const amount = Number(value || 0);
    if (Number.isNaN(amount)) return `0,00 \u20ac`;
    return `${amount.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} \u20ac`;
};

const escapeHtml = (value) => String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

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
            activateTab(btn.getAttribute("data-tab-target"));
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

function setupPaymentsWorkspace() {
    const form = document.querySelector('#tab-new form[action]');
    if (!form) return;

    const modalEl = document.getElementById("payment-confirm-modal");
    paymentUiState.confirmModal = modalEl && window.bootstrap?.Modal
        ? new window.bootstrap.Modal(modalEl)
        : null;

    bindInvoiceWorkspaceEvents();
    bindPaymentFormSubmission(form);
    initializeVisibleRows();
    captureSelectionsFromVisibleRows();
    initializeEntityFilterFromSelections();
    applyPresetPayment();
    refreshInvoiceWorkspace();
}

function bindInvoiceWorkspaceEvents() {
    const invoiceListContainer = document.getElementById("invoice-list-container");
    const searchInput = document.getElementById("invoice-search");
    const searchSubmit = document.getElementById("invoice-search-submit");
    const searchReset = document.getElementById("invoice-search-reset");
    const dateInput = document.getElementById("invoice-date");
    const chipRemove = document.getElementById("invoice-entity-chip-remove");
    const confirmSubmitButton = document.getElementById("payment-confirm-submit");

    invoiceListContainer?.addEventListener("click", (event) => {
        const paginationLink = event.target.closest(".invoice-pagination a.page-link");
        if (paginationLink) {
            const pageItem = paginationLink.closest(".page-item");
            if (pageItem?.classList.contains("disabled") || paginationLink.getAttribute("href") === "#") {
                event.preventDefault();
                return;
            }
            event.preventDefault();
            loadInvoiceList(paginationLink.href);
            return;
        }

        const row = event.target.closest(".invoice-row");
        if (!row || !invoiceListContainer.contains(row)) return;
        if (event.target.closest("a, button, input, label, select, textarea")) return;

        const checkbox = getRowCheckbox(row);
        if (!checkbox || checkbox.disabled) return;
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    });

    invoiceListContainer?.addEventListener("change", (event) => {
        const checkbox = event.target.closest('input[name="payment_id"]');
        if (checkbox) {
            handleRowCheckboxChange(checkbox);
            return;
        }

        if (isAmountInput(event.target)) {
            handleRowAmountChange(event.target);
        }
    });

    invoiceListContainer?.addEventListener("input", (event) => {
        if (isAmountInput(event.target)) {
            handleRowAmountChange(event.target, { realtime: true });
        }
    });

    searchSubmit?.addEventListener("click", () => {
        submitInvoiceSearch();
    });

    searchInput?.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        submitInvoiceSearch();
    });

    searchReset?.addEventListener("click", (event) => {
        event.preventDefault();
        resetInvoiceSearch();
    });

    chipRemove?.addEventListener("click", (event) => {
        event.preventDefault();
        clearEntityFilter();
    });

    dateInput?.addEventListener("change", () => {
        applyVisibleFilters();
    });
    dateInput?.addEventListener("input", () => {
        applyVisibleFilters();
    });

    confirmSubmitButton?.addEventListener("click", () => {
        const form = document.querySelector('#tab-new form[action]');
        if (!form) return;
        paymentUiState.bypassConfirmation = true;
        paymentUiState.confirmModal?.hide();
        form.requestSubmit();
    });
}

function bindPaymentFormSubmission(form) {
    form.addEventListener("submit", (event) => {
        if (paymentUiState.bypassConfirmation) {
            paymentUiState.bypassConfirmation = false;
            prepareHiddenSelectionInputs(form);
            return;
        }

        if (!paymentUiState.selections.size) {
            return;
        }

        if (!paymentUiState.confirmModal) {
            prepareHiddenSelectionInputs(form);
            return;
        }

        event.preventDefault();
        renderConfirmationModal();
        paymentUiState.confirmModal.show();
    });
}

function submitInvoiceSearch() {
    const searchInput = document.getElementById("invoice-search");
    if (!searchInput) return;

    const url = new URL(window.location.href);
    const query = (searchInput.value || "").trim();
    if (query) {
        url.searchParams.set("invoice_q", query);
    } else {
        url.searchParams.delete("invoice_q");
    }
    url.searchParams.set("invoice_page", "1");
    url.searchParams.set("tab", "tab-new");
    loadInvoiceList(url);
}

function resetInvoiceSearch() {
    const resetLink = document.getElementById("invoice-search-reset");
    const fallbackUrl = resetLink?.getAttribute("href") || window.location.href;
    loadInvoiceList(fallbackUrl);
}

async function loadInvoiceList(targetUrl) {
    const invoiceListContainer = document.getElementById("invoice-list-container");
    const searchInput = document.getElementById("invoice-search");
    const searchSubmit = document.getElementById("invoice-search-submit");
    const searchReset = document.getElementById("invoice-search-reset");
    if (!invoiceListContainer) return;

    const baseUrl = new URL(String(targetUrl), window.location.origin);
    baseUrl.hash = "tab-new";
    baseUrl.searchParams.delete("document_id");
    baseUrl.searchParams.delete("document_ids");
    baseUrl.searchParams.delete("amount");
    baseUrl.searchParams.delete("partial");
    baseUrl.searchParams.set("tab", "tab-new");

    const fetchUrl = new URL(baseUrl.toString());
    fetchUrl.searchParams.set(
        invoiceListContainer.getAttribute("data-partial-query-param") || "partial",
        invoiceListContainer.getAttribute("data-partial-query-value") || "invoice-list",
    );
    const selectedDocumentIds = getSelectedDocumentIds();
    if (selectedDocumentIds.length) {
        fetchUrl.searchParams.set("selected_document_ids", selectedDocumentIds.join(","));
    }

    if (paymentUiState.invoiceFetchController) {
        paymentUiState.invoiceFetchController.abort();
    }
    paymentUiState.invoiceFetchController = new AbortController();

    paymentUiState.invoiceLoading = true;
    invoiceListContainer.setAttribute("aria-busy", "true");
    invoiceListContainer.style.opacity = "0.55";
    if (searchInput) searchInput.disabled = true;
    if (searchSubmit) searchSubmit.disabled = true;
    if (searchReset) searchReset.classList.add("disabled");

    try {
        const response = await fetch(fetchUrl.toString(), {
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
            signal: paymentUiState.invoiceFetchController.signal,
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        invoiceListContainer.innerHTML = await response.text();
        initializeVisibleRows();
        applySelectionStateToVisibleRows();
        applyVisibleFilters();
        reorderVisibleRows();
        updateSelectionSummary();
        updateSearchControls(baseUrl);

        history.replaceState(null, "", `${baseUrl.pathname}${baseUrl.search}${baseUrl.hash}`);
    } catch (error) {
        if (error.name !== "AbortError") {
            window.location.assign(baseUrl.toString());
        }
    } finally {
        paymentUiState.invoiceLoading = false;
        paymentUiState.invoiceFetchController = null;
        invoiceListContainer.removeAttribute("aria-busy");
        invoiceListContainer.style.opacity = "";
        if (searchInput) searchInput.disabled = false;
        if (searchSubmit) searchSubmit.disabled = false;
        if (searchReset) searchReset.classList.remove("disabled");
    }
}

function updateSearchControls(currentUrl) {
    const searchInput = document.getElementById("invoice-search");
    const searchReset = document.getElementById("invoice-search-reset");
    const currentQuery = currentUrl.searchParams.get("invoice_q") || "";
    if (searchInput) {
        searchInput.value = currentQuery;
    }
    if (searchReset) {
        const resetUrl = new URL(currentUrl.toString());
        resetUrl.searchParams.delete("invoice_q");
        resetUrl.searchParams.delete("invoice_page");
        resetUrl.searchParams.set("tab", "tab-new");
        searchReset.setAttribute("href", `${resetUrl.pathname}${resetUrl.search}#tab-new`);
        searchReset.classList.toggle("d-none", !currentQuery);
    }
}

function getInvoiceRows() {
    return Array.from(document.querySelectorAll(".invoice-row"));
}

function getRowCheckbox(row) {
    return row?.querySelector('input[name="payment_id"]') || null;
}

function getRowAmountInput(row) {
    const checkbox = getRowCheckbox(row);
    if (!row || !checkbox) return null;
    return row.querySelector(`input[name="amount_${checkbox.value}"]`);
}

function isAmountInput(element) {
    return Boolean(element?.name && /^amount_\d+$/.test(element.name));
}

function getRowDocumentId(row) {
    return String(row?.getAttribute("data-document-id") || "").trim();
}

function initializeVisibleRows() {
    getInvoiceRows().forEach((row, index) => {
        row.dataset.originalOrder = String(index);
    });
}

function captureSelectionsFromVisibleRows() {
    getInvoiceRows().forEach((row) => {
        const checkbox = getRowCheckbox(row);
        if (!checkbox?.checked) return;
        upsertSelectionFromRow(row, { preserveOrder: false });
    });
}

function initializeEntityFilterFromSelections() {
    if (paymentUiState.activeEntityId || !paymentUiState.selections.size) {
        return;
    }
    const firstSelection = getSelectionItems().sort((left, right) => left.selectedOrder - right.selectedOrder)[0];
    if (!firstSelection?.legalEntityId) return;
    paymentUiState.activeEntityId = firstSelection.legalEntityId;
    paymentUiState.activeEntityName = firstSelection.legalEntityName || "";
}

function upsertSelectionFromRow(row, options = {}) {
    const documentId = getRowDocumentId(row);
    if (!documentId) return null;

    const checkbox = getRowCheckbox(row);
    const amountInput = getRowAmountInput(row);
    const existing = paymentUiState.selections.get(documentId);
    const shouldPreserveOrder = options.preserveOrder !== false;
    let amountValue = (amountInput?.value || "").trim();

    if (!amountValue) {
        amountValue = existing?.amount || row.getAttribute("data-due") || "";
        if (amountInput && amountValue) {
            amountInput.value = amountValue;
        }
    }

    const selection = {
        documentId,
        documentLabel: row.getAttribute("data-document-label") || `Documento #${documentId}`,
        supplierName: row.getAttribute("data-supplier-name") || "Fornitore non disponibile",
        legalEntityId: row.getAttribute("data-legal-entity-id") || "",
        legalEntityName: row.getAttribute("data-legal-entity-name") || "",
        amount: amountValue,
        selectedOrder: shouldPreserveOrder && existing
            ? existing.selectedOrder
            : ++paymentUiState.selectionSequence,
    };

    if (checkbox) {
        checkbox.checked = true;
    }
    paymentUiState.selections.set(documentId, selection);
    return selection;
}

function removeSelection(documentId) {
    paymentUiState.selections.delete(String(documentId));
}

function handleRowCheckboxChange(checkbox) {
    const row = checkbox.closest(".invoice-row");
    if (!row) return;

    if (checkbox.checked) {
        upsertSelectionFromRow(row, { preserveOrder: false });
        if (!paymentUiState.activeEntityId) {
            const entityId = row.getAttribute("data-legal-entity-id") || "";
            const entityName = row.getAttribute("data-legal-entity-name") || "";
            if (entityId) {
                paymentUiState.activeEntityId = entityId;
                paymentUiState.activeEntityName = entityName;
            }
        }
    } else {
        removeSelection(getRowDocumentId(row));
    }

    refreshInvoiceWorkspace();
}

function handleRowAmountChange(input, options = {}) {
    const row = input.closest(".invoice-row");
    if (!row) return;

    const checkbox = getRowCheckbox(row);
    if (checkbox?.checked) {
        upsertSelectionFromRow(row, { preserveOrder: true });
    }

    if (options.realtime) {
        updateSelectionSummary();
        return;
    }
    refreshInvoiceWorkspace();
}

function applySelectionStateToVisibleRows() {
    getInvoiceRows().forEach((row) => {
        const documentId = getRowDocumentId(row);
        const checkbox = getRowCheckbox(row);
        const amountInput = getRowAmountInput(row);
        const selection = paymentUiState.selections.get(documentId);

        if (checkbox) {
            checkbox.checked = Boolean(selection);
        }
        if (amountInput) {
            if (selection?.amount) {
                amountInput.value = selection.amount;
            } else if (!selection && amountInput.defaultValue) {
                amountInput.value = amountInput.defaultValue;
            }
        }

        row.dataset.selectedOrder = selection ? String(selection.selectedOrder) : "0";
        row.classList.toggle("invoice-row-selected", Boolean(selection));
    });
}

function reorderVisibleRows() {
    const invoiceBody = document.querySelector(".invoice-body");
    if (!invoiceBody) return;

    const orderedRows = getInvoiceRows().sort((leftRow, rightRow) => {
        const leftSelection = paymentUiState.selections.get(getRowDocumentId(leftRow));
        const rightSelection = paymentUiState.selections.get(getRowDocumentId(rightRow));
        const leftChecked = Boolean(leftSelection);
        const rightChecked = Boolean(rightSelection);

        if (leftChecked !== rightChecked) {
            return leftChecked ? -1 : 1;
        }
        if (leftChecked && rightChecked) {
            return rightSelection.selectedOrder - leftSelection.selectedOrder;
        }
        return Number(leftRow.dataset.originalOrder || "0") - Number(rightRow.dataset.originalOrder || "0");
    });

    orderedRows.forEach((row) => invoiceBody.appendChild(row));
}

function updateEntityFilterChip() {
    const chip = document.getElementById("invoice-entity-chip");
    const chipLabel = document.getElementById("invoice-entity-chip-label");
    if (!chip || !chipLabel) return;

    if (!paymentUiState.activeEntityId) {
        chip.classList.add("d-none");
        chipLabel.textContent = "";
        return;
    }

    chipLabel.textContent = paymentUiState.activeEntityName
        ? `Intestatario: ${paymentUiState.activeEntityName}`
        : "Intestatario";
    chip.classList.remove("d-none");
}

function updateBankAccounts() {
    const ibanSelect = document.getElementById("bank-account-iban");
    const ibanEmptyOption = document.getElementById("bank-account-empty");
    if (!ibanSelect) return;

    const entityId = paymentUiState.activeEntityId;
    const options = Array.from(ibanSelect.querySelectorAll("option")).filter((option) => option.value);
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
        const showEmpty = Boolean(entityId) && visibleCount === 0;
        ibanEmptyOption.hidden = !showEmpty;
        ibanEmptyOption.disabled = !showEmpty;
    }

    if (ibanSelect.value) {
        const selected = options.find((option) => option.value === ibanSelect.value);
        if (selected && selected.hidden) {
            ibanSelect.value = "";
        }
    }

    refreshSelect2(ibanSelect);
}

function applyVisibleFilters() {
    const dateInput = document.getElementById("invoice-date");
    const dateValue = (dateInput?.value || "").trim();

    getInvoiceRows().forEach((row) => {
        const rowDate = row.getAttribute("data-date") || "";
        const rowEntity = row.getAttribute("data-legal-entity-id") || "";
        const matchDate = !dateValue || rowDate === dateValue;
        const matchEntity = !paymentUiState.activeEntityId || rowEntity === paymentUiState.activeEntityId;
        row.classList.toggle("d-none", !(matchDate && matchEntity));
    });
}

function clearEntityFilter() {
    paymentUiState.activeEntityId = null;
    paymentUiState.activeEntityName = "";
    refreshInvoiceWorkspace();
}

function refreshInvoiceWorkspace() {
    applySelectionStateToVisibleRows();
    updateEntityFilterChip();
    updateBankAccounts();
    applyVisibleFilters();
    reorderVisibleRows();
    updateSelectionSummary();
}

function getSelectionItems() {
    return Array.from(paymentUiState.selections.values()).sort(
        (left, right) => right.selectedOrder - left.selectedOrder
    );
}

function getSelectedDocumentIds() {
    return getSelectionItems().map((item) => item.documentId).filter(Boolean);
}

function updateSelectionSummary() {
    const summaryCount = document.getElementById("payment-selected-count");
    const summaryTotal = document.getElementById("payment-selected-total");
    const summarySuppliers = document.getElementById("payment-selected-suppliers");
    const items = getSelectionItems();
    const total = items.reduce((sum, item) => {
        const amount = Number(String(item.amount || "").replace(",", "."));
        return sum + (Number.isNaN(amount) ? 0 : amount);
    }, 0);
    const supplierNames = Array.from(new Set(items.map((item) => item.supplierName).filter(Boolean)));

    if (summaryCount) summaryCount.textContent = String(items.length);
    if (summaryTotal) summaryTotal.innerHTML = formatCurrency(total);
    if (summarySuppliers) {
        if (!supplierNames.length) {
            summarySuppliers.textContent = "Nessun fornitore selezionato";
        } else if (supplierNames.length === 1) {
            summarySuppliers.textContent = supplierNames[0];
        } else {
            summarySuppliers.textContent = `${supplierNames.length} fornitori selezionati`;
        }
    }
}

function renderConfirmationModal() {
    const confirmCount = document.getElementById("payment-confirm-count");
    const confirmSupplierCount = document.getElementById("payment-confirm-supplier-count");
    const confirmTotal = document.getElementById("payment-confirm-total");
    const confirmGroups = document.getElementById("payment-confirm-groups");
    const items = getSelectionItems();
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
        const amount = Number(String(item.amount || "").replace(",", "."));
        group.total += Number.isNaN(amount) ? 0 : amount;
        group.count += 1;
        group.items.push(item);
    });

    const total = Array.from(groupedBySupplier.values()).reduce((sum, group) => sum + group.total, 0);

    if (confirmCount) confirmCount.textContent = String(items.length);
    if (confirmSupplierCount) confirmSupplierCount.textContent = String(groupedBySupplier.size);
    if (confirmTotal) confirmTotal.innerHTML = formatCurrency(total);
    if (!confirmGroups) return;

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

function prepareHiddenSelectionInputs(form) {
    const hiddenContainer = document.getElementById("payment-selection-hidden-inputs");
    if (!hiddenContainer) return;

    hiddenContainer.innerHTML = "";
    form.querySelectorAll('.invoice-row input[name="payment_id"], .invoice-row input[name^="amount_"]').forEach((input) => {
        input.disabled = true;
    });

    getSelectionItems().forEach((item) => {
        const paymentIdInput = document.createElement("input");
        paymentIdInput.type = "hidden";
        paymentIdInput.name = "payment_id";
        paymentIdInput.value = item.documentId;
        hiddenContainer.appendChild(paymentIdInput);

        const amountInput = document.createElement("input");
        amountInput.type = "hidden";
        amountInput.name = `amount_${item.documentId}`;
        amountInput.value = item.amount || "";
        hiddenContainer.appendChild(amountInput);
    });
}

function applyPresetPayment() {
    const params = new URLSearchParams(window.location.search);
    const docId = params.get("document_id");
    const docIdsRaw = params.get("document_ids");
    const docIds = docIdsRaw
        ? docIdsRaw.split(",").map((value) => value.trim()).filter(Boolean)
        : [];
    const targetIds = docId ? [docId, ...docIds.filter((value) => value !== docId)] : docIds;
    if (!targetIds.length) return;

    targetIds.forEach((targetDocId) => {
        const row = document.querySelector(`.invoice-row[data-document-id="${targetDocId}"]`);
        if (row) {
            row.classList.add("border", "border-primary", "rounded");
        }
    });

    const firstRow = document.querySelector(`.invoice-row[data-document-id="${targetIds[0]}"]`);
    if (firstRow) {
        firstRow.scrollIntoView({ behavior: "smooth", block: "center" });
    }
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

        if (!file) {
            previewFrame.removeAttribute("src");
            placeholderDiv.classList.remove("d-none");
            return;
        }

        if (file.type !== "application/pdf") {
            alert("Solo file PDF sono consentiti.");
            fileInput.value = "";
            return;
        }

        const maxSize = 10 * 1024 * 1024;
        if (file.size > maxSize) {
            alert("File troppo grande. Massimo 10MB consentito.");
            fileInput.value = "";
            return;
        }

        const url = URL.createObjectURL(file);
        previewFrame.src = url;
        placeholderDiv.classList.add("d-none");

        previewFrame.addEventListener("load", () => {
            URL.revokeObjectURL(url);
        }, { once: true });

        setTimeout(() => {
            try {
                const doc = previewFrame.contentDocument;
                if (!doc || doc.body.innerHTML === "") {
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
            } catch (error) {
                console.debug("PDF preview loaded (cross-origin check blocked)");
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

        if (!targetDocId && paymentUiState.selections.size === 1) {
            targetDocId = getSelectionItems()[0]?.documentId || null;
        }

        if (targetDocId) {
            const amountInput = document.querySelector(`input[name="amount_${targetDocId}"]`);
            if (amountInput && amountValue) {
                amountInput.value = amountValue;
                amountInput.dispatchEvent(new Event("input", { bubbles: true }));
                amountInput.dispatchEvent(new Event("change", { bubbles: true }));
                if (badge) badge(amountInput, fields.amount.confidence || 0, "OCR");
            } else {
                const currentSelection = paymentUiState.selections.get(String(targetDocId));
                if (currentSelection) {
                    currentSelection.amount = amountValue;
                    paymentUiState.selections.set(String(targetDocId), currentSelection);
                    updateSelectionSummary();
                }
            }
        }
    }
}
