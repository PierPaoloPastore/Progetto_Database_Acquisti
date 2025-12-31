document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("schedule-search");
    const statusSelect = document.getElementById("schedule-status");
    const dateFromInput = document.getElementById("schedule-date-from");
    const dateToInput = document.getElementById("schedule-date-to");
    const amountMinInput = document.getElementById("schedule-amount-min");
    const amountMaxInput = document.getElementById("schedule-amount-max");
    const rows = document.querySelectorAll("[data-schedule-row]");
    const groups = document.querySelectorAll("[data-schedule-group]");
    const emptyRow = document.getElementById("schedule-empty");

    if (!searchInput && !statusSelect) return;

    const applyFilter = () => {
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
            if (visible) visibleCount += 1;
        });

        if (groups.length) {
            groups.forEach((group) => {
                const groupRows = group.querySelectorAll("[data-schedule-row]");
                const hasVisible = Array.from(groupRows).some((row) => !row.classList.contains("d-none"));
                group.classList.toggle("d-none", !hasVisible);
            });
        }

        if (emptyRow) {
            emptyRow.classList.toggle("d-none", visibleCount !== 0);
        }
    };

    searchInput?.addEventListener("keyup", applyFilter);
    statusSelect?.addEventListener("change", applyFilter);
    dateFromInput?.addEventListener("change", applyFilter);
    dateToInput?.addEventListener("change", applyFilter);
    amountMinInput?.addEventListener("input", applyFilter);
    amountMaxInput?.addEventListener("input", applyFilter);
});
