document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-import-details]").forEach(section => {
        const select = section.querySelector("[data-outcome-filter]");
        const search = section.querySelector("[data-detail-search]");
        const count = section.querySelector("[data-detail-count]");
        if (!select || !search || !count) return;
        const update = () => {
            const rows = Array.from(section.querySelectorAll("tbody tr[data-category]"));
            let visible = 0;
            const counts = { all: rows.length, problems: 0, success: 0, duplicate: 0, warning: 0 };
            rows.forEach(row => {
                counts[row.dataset.category] += 1;
                row.hidden = (select.value !== "all" && row.dataset.category !== select.value)
                    || !row.textContent.toLocaleLowerCase().includes(search.value.toLocaleLowerCase());
                if (!row.hidden) visible += 1;
            });
            Array.from(select.options).forEach(option => {
                option.dataset.label ||= option.textContent;
                option.textContent = `${option.dataset.label} (${counts[option.value]})`;
            });
            count.textContent = `${visible} di ${rows.length} file mostrati`;
        };
        const reset = () => {
            select.value = section.querySelector('tr[data-category="problems"]') ? "problems" : "all";
            search.value = "";
            update();
        };
        select.addEventListener("change", update);
        search.addEventListener("input", update);
        section.addEventListener("import-details-updated", reset);
        reset();
    });
});
