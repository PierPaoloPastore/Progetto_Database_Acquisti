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
