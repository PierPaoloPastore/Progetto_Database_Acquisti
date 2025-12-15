document.addEventListener("DOMContentLoaded", () => {
    setupTabSwitching();
    setupInvoiceFilter();
    setupPdfPreview();
});

function setupTabSwitching() {
    const tabButtons = document.querySelectorAll("[data-tab-target]");
    const sections = document.querySelectorAll(".tab-section");

    tabButtons.forEach((btn) => {
        btn.addEventListener("click", (event) => {
            event.preventDefault();
            const target = btn.getAttribute("data-tab-target");

            tabButtons.forEach((b) => b.classList.remove("active"));
            btn.classList.add("active");

            sections.forEach((section) => {
                if (section.id === target) {
                    section.classList.remove("d-none");
                } else {
                    section.classList.add("d-none");
                }
            });
        });
    });
}

function setupInvoiceFilter() {
    const searchInput = document.getElementById("invoice-search");
    const rows = document.querySelectorAll(".invoice-row");

    if (!searchInput) return;

    searchInput.addEventListener("keyup", () => {
        const query = searchInput.value.toLowerCase();

        rows.forEach((row) => {
            const text = row.getAttribute("data-search") || row.textContent;
            const match = text.toLowerCase().includes(query);
            row.classList.toggle("d-none", !match);
        });
    });
}

function setupPdfPreview() {
    const fileInput = document.getElementById("pdf-file");
    const previewFrame = document.getElementById("pdf-preview");

    if (!fileInput || !previewFrame) return;

    fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];
        if (file) {
            const url = URL.createObjectURL(file);
            previewFrame.src = url;
        } else {
            previewFrame.removeAttribute("src");
        }
    });
}
