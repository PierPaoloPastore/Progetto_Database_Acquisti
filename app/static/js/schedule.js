document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("schedule-search");
    const statusSelect = document.getElementById("schedule-status");
    const dateFromInput = document.getElementById("schedule-date-from");
    const dateToInput = document.getElementById("schedule-date-to");
    const amountMinInput = document.getElementById("schedule-amount-min");
    const amountMaxInput = document.getElementById("schedule-amount-max");
    const rangeButtons = document.querySelectorAll("[data-range]");
    const presetButtons = document.querySelectorAll("[data-preset]");
    const resetButtons = document.querySelectorAll("[data-reset-filters]");
    const rows = Array.from(document.querySelectorAll("[data-schedule-row]"));
    const groups = document.querySelectorAll("[data-schedule-group]");
    const emptyStates = document.querySelectorAll("[data-schedule-empty]");
    const bulkBar = document.getElementById("schedule-bulk-bar");
    const bulkCount = bulkBar?.querySelector("[data-bulk-count]");
    const bulkTotal = bulkBar?.querySelector("[data-bulk-total]");
    const paymentIndexUrl = bulkBar?.getAttribute("data-payment-index-url") || "/payments/";
    const selectAllCheckboxes = document.querySelectorAll(".schedule-select-all");
    const rowCheckboxes = document.querySelectorAll(".schedule-select");
    const sortHeaders = document.querySelectorAll("[data-sort]");
    const toolbar = document.querySelector("[data-schedule-toolbar]");

    if (!rows.length || (!searchInput && !statusSelect)) return;

    const storageKey = "schedule_filters_v1";
    const defaultSort = { key: null, dir: "asc" };
    const sortState = { ...defaultSort };

    const todayIso = toolbar?.getAttribute("data-today") || "";
    const range7Iso = toolbar?.getAttribute("data-range-7") || "";
    const range30Iso = toolbar?.getAttribute("data-range-30") || "";

    const formatAmountValue = (value) => {
        if (Number.isNaN(value)) return "0,00";
        return value.toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };

    const formatAmount = (value) => `${formatAmountValue(value)} \u20ac`;
    const formatCount = (value) => value.toLocaleString("it-IT");

    const readFiltersFromInputs = () => ({
        q: (searchInput?.value || "").trim(),
        status: statusSelect?.value || "all",
        date_from: dateFromInput?.value || "",
        date_to: dateToInput?.value || "",
        amount_min: amountMinInput?.value || "",
        amount_max: amountMaxInput?.value || "",
        sort: sortState.key || "",
        dir: sortState.dir || "",
    });

    const applyFilters = ({ updateUrl = true, save = true } = {}) => {
        const query = (searchInput?.value || "").toLowerCase();
        const status = statusSelect?.value || "all";
        const dateFrom = dateFromInput?.value || "";
        const dateTo = dateToInput?.value || "";
        const amountMinRaw = amountMinInput?.value || "";
        const amountMaxRaw = amountMaxInput?.value || "";
        const amountMin = amountMinRaw ? Number(amountMinRaw) : null;
        const amountMax = amountMaxRaw ? Number(amountMaxRaw) : null;
        let visibleCount = 0;

        rows.forEach((row) => {
            const text = (row.getAttribute("data-search") || "").toLowerCase();
            const rowStatus = row.getAttribute("data-status") || "";
            const rowDate = row.getAttribute("data-due-date") || "";
            const amountValue = Number(row.getAttribute("data-amount") || "0");
            const matchText = !query || text.includes(query);
            const matchStatus = status === "all" || rowStatus === status;
            let matchDate = true;

            if (status !== "no_due" && (dateFrom || dateTo)) {
                if (!rowDate) {
                    matchDate = false;
                } else {
                    if (dateFrom && rowDate < dateFrom) {
                        matchDate = false;
                    }
                    if (dateTo && rowDate > dateTo) {
                        matchDate = false;
                    }
                }
            }

            let matchAmount = true;
            if (amountMin !== null && !Number.isNaN(amountMin)) {
                matchAmount = amountValue >= amountMin;
            }
            if (matchAmount && amountMax !== null && !Number.isNaN(amountMax)) {
                matchAmount = amountValue <= amountMax;
            }

            const visible = matchText && matchStatus && matchDate && matchAmount;
            row.classList.toggle("d-none", !visible);

            const checkbox = row.querySelector(".schedule-select");
            if (!visible && checkbox) {
                checkbox.checked = false;
            }

            if (visible) visibleCount += 1;
        });

        if (groups.length) {
            groups.forEach((group) => {
                const groupRows = group.querySelectorAll("[data-schedule-row]");
                const hasVisible = Array.from(groupRows).some((row) => !row.classList.contains("d-none"));
                group.classList.toggle("d-none", !hasVisible);
            });
        }

        emptyStates.forEach((emptyState) => {
            emptyState.classList.toggle("d-none", visibleCount !== 0);
        });

        updateGroupSummaries();
        updateSelectAllState();
        updateBulkBar();

        if (updateUrl) {
            updateQueryString();
        }
        if (save) {
            saveFilters();
        }
    };

    const updateQueryString = () => {
        const filters = readFiltersFromInputs();
        const params = new URLSearchParams();

        if (filters.q) params.set("q", filters.q);
        if (filters.status && filters.status !== "all") params.set("status", filters.status);
        if (filters.date_from) params.set("date_from", filters.date_from);
        if (filters.date_to) params.set("date_to", filters.date_to);
        if (filters.amount_min) params.set("amount_min", filters.amount_min);
        if (filters.amount_max) params.set("amount_max", filters.amount_max);
        if (filters.sort) {
            params.set("sort", filters.sort);
            if (filters.dir) {
                params.set("dir", filters.dir);
            }
        }

        const next = params.toString();
        const nextUrl = next ? `${window.location.pathname}?${next}` : window.location.pathname;
        window.history.replaceState(null, "", nextUrl);
    };

    const saveFilters = () => {
        const filters = readFiltersFromInputs();
        window.localStorage.setItem(storageKey, JSON.stringify(filters));
    };

    const setFilters = (filters) => {
        if (searchInput && typeof filters.q === "string") searchInput.value = filters.q;
        if (statusSelect && filters.status) statusSelect.value = filters.status;
        if (dateFromInput && typeof filters.date_from === "string") dateFromInput.value = filters.date_from;
        if (dateToInput && typeof filters.date_to === "string") dateToInput.value = filters.date_to;
        if (amountMinInput && typeof filters.amount_min === "string") amountMinInput.value = filters.amount_min;
        if (amountMaxInput && typeof filters.amount_max === "string") amountMaxInput.value = filters.amount_max;
    };

    const loadFiltersFromStorage = () => {
        const raw = window.localStorage.getItem(storageKey);
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch (err) {
            return null;
        }
    };

    const parseQueryFilters = () => {
        const params = new URLSearchParams(window.location.search);
        return {
            q: params.get("q") || "",
            status: params.get("status") || "all",
            date_from: params.get("date_from") || "",
            date_to: params.get("date_to") || "",
            amount_min: params.get("amount_min") || "",
            amount_max: params.get("amount_max") || "",
            sort: params.get("sort") || "",
            dir: params.get("dir") || "",
        };
    };

    const applyRangePreset = (range) => {
        if (!dateFromInput || !dateToInput) return;
        if (range === "today") {
            dateFromInput.value = todayIso;
            dateToInput.value = todayIso;
        } else if (range === "7") {
            dateFromInput.value = todayIso;
            dateToInput.value = range7Iso;
        } else if (range === "30") {
            dateFromInput.value = todayIso;
            dateToInput.value = range30Iso;
        }
    };

    const applyPreset = (preset) => {
        if (preset === "overdue") {
            if (statusSelect) statusSelect.value = "overdue";
            if (dateFromInput) dateFromInput.value = "";
            if (dateToInput) dateToInput.value = "";
        } else if (preset === "due_soon") {
            if (statusSelect) statusSelect.value = "all";
            applyRangePreset("7");
        } else if (preset === "no_due") {
            if (statusSelect) statusSelect.value = "no_due";
            if (dateFromInput) dateFromInput.value = "";
            if (dateToInput) dateToInput.value = "";
        } else if (preset === "high_amount") {
            if (amountMinInput) amountMinInput.value = "5000";
        }
        applyFilters();
    };

    const updateSortIcons = () => {
        sortHeaders.forEach((header) => {
            const icon = header.querySelector(".sort-icon");
            if (!icon) return;
            if (header.getAttribute("data-sort") !== sortState.key) {
                icon.className = "bi bi-arrow-down-up sort-icon";
                return;
            }
            icon.className = sortState.dir === "desc" ? "bi bi-arrow-down sort-icon" : "bi bi-arrow-up sort-icon";
        });
    };

    const statusPriority = {
        overdue: 0,
        due_soon: 1,
        scheduled: 2,
        no_due: 3,
    };

    const sortTableRows = (table, key, dir) => {
        const body = table.querySelector("tbody");
        if (!body) return;
        const tableRows = Array.from(body.querySelectorAll("[data-schedule-row]"));

        const compare = (a, b) => {
            if (!key) {
                const statusA = statusPriority[a.getAttribute("data-status")] ?? 9;
                const statusB = statusPriority[b.getAttribute("data-status")] ?? 9;
                if (statusA !== statusB) return statusA - statusB;

                const dateA = a.getAttribute("data-due-date") || "";
                const dateB = b.getAttribute("data-due-date") || "";
                if (dateA !== dateB) {
                    if (!dateA) return 1;
                    if (!dateB) return -1;
                    return dateA.localeCompare(dateB);
                }

                const remA = Number(a.getAttribute("data-remaining") || "0");
                const remB = Number(b.getAttribute("data-remaining") || "0");
                if (remA !== remB) return remB - remA;
            }

            if (key === "due_date") {
                const dateA = a.getAttribute("data-due-date") || "";
                const dateB = b.getAttribute("data-due-date") || "";
                if (dateA !== dateB) {
                    if (!dateA) return 1;
                    if (!dateB) return -1;
                    return dateA.localeCompare(dateB);
                }
            }

            if (key === "remaining") {
                const remA = Number(a.getAttribute("data-remaining") || "0");
                const remB = Number(b.getAttribute("data-remaining") || "0");
                if (remA !== remB) return remA - remB;
            }

            if (key === "total") {
                const totA = Number(a.getAttribute("data-total") || "0");
                const totB = Number(b.getAttribute("data-total") || "0");
                if (totA !== totB) return totA - totB;
            }

            const idA = Number(a.getAttribute("data-doc-id") || "0");
            const idB = Number(b.getAttribute("data-doc-id") || "0");
            return idA - idB;
        };

        tableRows.sort((a, b) => {
            const result = compare(a, b);
            if (!key) return result;
            return dir === "desc" ? -result : result;
        });

        tableRows.forEach((row) => body.appendChild(row));
    };

    const applySorting = () => {
        document.querySelectorAll(".schedule-table").forEach((table) => {
            sortTableRows(table, sortState.key, sortState.dir || "asc");
        });
        updateSortIcons();
    };

    const updateSelectAllState = () => {
        selectAllCheckboxes.forEach((headerCheckbox) => {
            const table = headerCheckbox.closest("table");
            if (!table) return;
            const visibleRows = Array.from(table.querySelectorAll("[data-schedule-row]")).filter(
                (row) => !row.classList.contains("d-none")
            );
            const visibleChecks = visibleRows
                .map((row) => row.querySelector(".schedule-select"))
                .filter(Boolean);
            const allChecked = visibleChecks.length > 0 && visibleChecks.every((checkbox) => checkbox.checked);
            headerCheckbox.checked = allChecked;
        });
    };

    const updateGroupSummaries = () => {
        groups.forEach((group) => {
            const visibleRows = Array.from(group.querySelectorAll("[data-schedule-row]")).filter(
                (row) => !row.classList.contains("d-none")
            );
            const totalCount = visibleRows.length;
            let overdueCount = 0;
            let dueSoonCount = 0;
            let totalAmount = 0;

            visibleRows.forEach((row) => {
                const status = row.getAttribute("data-status");
                if (status === "overdue") overdueCount += 1;
                if (status === "due_soon") dueSoonCount += 1;
                totalAmount += Number(row.getAttribute("data-remaining") || "0");
            });

            const totalEl = group.querySelector("[data-group-count]");
            if (totalEl) totalEl.textContent = formatCount(totalCount);
            const overdueEl = group.querySelector("[data-group-overdue]");
            if (overdueEl) overdueEl.textContent = formatCount(overdueCount);
            const dueSoonEl = group.querySelector("[data-group-due-soon]");
            if (dueSoonEl) dueSoonEl.textContent = formatCount(dueSoonCount);
            const amountEl = group.querySelector("[data-group-amount]");
            if (amountEl) amountEl.textContent = formatAmountValue(totalAmount);
        });
    };

    const updateBulkBar = () => {
        if (!bulkBar) return;
        const selected = Array.from(rowCheckboxes).filter((checkbox) => checkbox.checked);
        const total = selected.reduce((sum, checkbox) => {
            const row = checkbox.closest("[data-schedule-row]");
            if (!row) return sum;
            const remaining = Number(row.getAttribute("data-remaining") || "0");
            return sum + remaining;
        }, 0);

        bulkBar.classList.toggle("d-none", selected.length === 0);
        if (bulkCount) bulkCount.textContent = selected.length.toString();
        if (bulkTotal) bulkTotal.textContent = formatAmount(total);
    };

    const handleRowClick = (event) => {
        const target = event.target;
        const row = target.closest("[data-schedule-row]");
        if (!row) return;
        if (target.closest("a, button, input, label, select, textarea")) return;
        const href = row.getAttribute("data-row-href");
        if (href) {
            window.location.href = href;
        }
    };

    document.addEventListener("click", handleRowClick);

    rowCheckboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            updateSelectAllState();
            updateBulkBar();
        });
    });

    selectAllCheckboxes.forEach((headerCheckbox) => {
        headerCheckbox.addEventListener("change", () => {
            const table = headerCheckbox.closest("table");
            if (!table) return;
            const visibleRows = Array.from(table.querySelectorAll("[data-schedule-row]")).filter(
                (row) => !row.classList.contains("d-none")
            );
            visibleRows.forEach((row) => {
                const checkbox = row.querySelector(".schedule-select");
                if (checkbox) {
                    checkbox.checked = headerCheckbox.checked;
                }
            });
            updateBulkBar();
        });
    });

    bulkBar?.addEventListener("click", (event) => {
        const target = event.target.closest("[data-bulk-action]");
        if (!target) return;
        const action = target.getAttribute("data-bulk-action");
        const selectedRows = Array.from(rowCheckboxes)
            .filter((checkbox) => checkbox.checked)
            .map((checkbox) => checkbox.closest("[data-schedule-row]"))
            .filter(Boolean);

        if (!selectedRows.length) return;

        if (action === "register") {
            const ids = selectedRows.map((row) => row.getAttribute("data-doc-id")).filter(Boolean);
            const url = new URL(paymentIndexUrl, window.location.origin);
            url.searchParams.set("document_ids", ids.join(","));
            url.searchParams.set("tab", "tab-new");
            window.location.href = url.toString();
            return;
        }

        if (action === "print") {
            const ids = selectedRows.map((row) => row.getAttribute("data-doc-id")).filter(Boolean);
            const form = document.getElementById("schedule-print-form");
            const input = document.getElementById("schedule-print-ids");
            if (!form || !input) {
                alert("Stampa PDF non ancora disponibile.");
                return;
            }
            input.value = ids.join(",");
            form.submit();
            return;
        }

        if (action === "export") {
            const header = ["document_id", "fornitore", "documento", "scadenza", "totale", "residuo", "stato"];
            const rowsCsv = selectedRows.map((row) => {
                const docId = row.getAttribute("data-doc-id") || "";
                const supplier = row.getAttribute("data-supplier-name") || "";
                const docNumber = row.getAttribute("data-document-number") || "";
                const dueDate = row.getAttribute("data-due-date") || "";
                const total = row.getAttribute("data-total") || "";
                const remaining = row.getAttribute("data-remaining") || "";
                const status = row.getAttribute("data-status") || "";
                return [docId, supplier, docNumber, dueDate, total, remaining, status]
                    .map((value) => `"${String(value).replace(/"/g, '""')}"`)
                    .join(",");
            });

            const csvContent = [header.join(","), ...rowsCsv].join("\n");
            const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.download = `scadenziario_${new Date().toISOString().slice(0, 10)}.csv`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    });

    sortHeaders.forEach((header) => {
        header.addEventListener("click", () => {
            const key = header.getAttribute("data-sort");
            if (!key) return;
            if (sortState.key === key) {
                sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
            } else {
                sortState.key = key;
                sortState.dir = "asc";
            }
            applySorting();
            updateQueryString();
            saveFilters();
        });
    });

    searchInput?.addEventListener("input", () => applyFilters());
    statusSelect?.addEventListener("change", () => applyFilters());
    dateFromInput?.addEventListener("change", () => applyFilters());
    dateToInput?.addEventListener("change", () => applyFilters());
    amountMinInput?.addEventListener("input", () => applyFilters());
    amountMaxInput?.addEventListener("input", () => applyFilters());

    rangeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const range = button.getAttribute("data-range");
            if (range === "custom") {
                dateFromInput?.focus();
                return;
            }
            applyRangePreset(range);
            applyFilters();
        });
    });

    presetButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const preset = button.getAttribute("data-preset");
            if (!preset) return;
            applyPreset(preset);
        });
    });

    resetButtons.forEach((button) => {
        button.addEventListener("click", () => {
            if (searchInput) searchInput.value = "";
            if (statusSelect) statusSelect.value = "all";
            if (dateFromInput) dateFromInput.value = "";
            if (dateToInput) dateToInput.value = "";
            if (amountMinInput) amountMinInput.value = "";
            if (amountMaxInput) amountMaxInput.value = "";
            sortState.key = null;
            sortState.dir = "asc";
            applySorting();
            applyFilters();
        });
    });

    const params = new URLSearchParams(window.location.search);
    const hasExplicitQuery = params.toString().length > 0;
    const queryFilters = parseQueryFilters();
    if (queryFilters.sort) {
        sortState.key = queryFilters.sort;
        sortState.dir = queryFilters.dir || "asc";
    }

    if (!hasExplicitQuery) {
        const storedFilters = loadFiltersFromStorage();
        if (storedFilters) {
            setFilters(storedFilters);
            if (storedFilters.sort) {
                sortState.key = storedFilters.sort;
                sortState.dir = storedFilters.dir || "asc";
            }
        }
    } else {
        setFilters(queryFilters);
    }

    applySorting();
    applyFilters({ updateUrl: !hasExplicitQuery });
});
