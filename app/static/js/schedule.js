document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("schedule-search");
    const statusSelect = document.getElementById("schedule-status");
    const rows = document.querySelectorAll("[data-schedule-row]");
    const emptyRow = document.getElementById("schedule-empty");

    if (!searchInput && !statusSelect) return;

    const applyFilter = () => {
        const query = (searchInput?.value || "").toLowerCase();
        const status = statusSelect?.value || "all";
        let visibleCount = 0;

        rows.forEach((row) => {
            const text = (row.getAttribute("data-search") || "").toLowerCase();
            const rowStatus = row.getAttribute("data-status") || "";
            const matchText = !query || text.includes(query);
            const matchStatus = status === "all" || rowStatus === status;
            const visible = matchText && matchStatus;

            row.classList.toggle("d-none", !visible);
            if (visible) visibleCount += 1;
        });

        if (emptyRow) {
            emptyRow.classList.toggle("d-none", visibleCount !== 0);
        }
    };

    searchInput?.addEventListener("keyup", applyFilter);
    statusSelect?.addEventListener("change", applyFilter);
});
