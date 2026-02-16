document.addEventListener("DOMContentLoaded", () => {
    const scrollLinks = document.querySelectorAll("[data-scroll-target]");
    scrollLinks.forEach((link) => {
        link.addEventListener("click", (event) => {
            const targetSelector = link.getAttribute("data-scroll-target");
            if (!targetSelector) {
                return;
            }
            const target = document.querySelector(targetSelector);
            if (!target) {
                return;
            }
            event.preventDefault();
            target.scrollIntoView({ behavior: "smooth", block: "start" });
            if (typeof target.focus === "function") {
                target.focus({ preventScroll: true });
            }
            target.classList.add("scroll-highlight");
            window.setTimeout(() => target.classList.remove("scroll-highlight"), 1200);
        });
    });

    const autosizeFields = document.querySelectorAll(".js-autoresize");
    const resize = (field) => {
        field.style.height = "auto";
        field.style.height = `${field.scrollHeight}px`;
    };
    autosizeFields.forEach((field) => {
        resize(field);
        field.addEventListener("input", () => resize(field));
    });

    const form = document.querySelector("[data-dirty-form]");
    if (form) {
        const submitBtn = form.querySelector("[data-dirty-submit]");
        const fields = form.querySelectorAll("input, select, textarea");
        const initialValues = new Map();

        const readValue = (field) => {
            if (field.type === "checkbox" || field.type === "radio") {
                return field.checked ? "1" : "0";
            }
            return (field.value || "").trim();
        };

        fields.forEach((field) => {
            initialValues.set(field, readValue(field));
        });

        const updateState = () => {
            const isDirty = Array.from(fields).some(
                (field) => readValue(field) !== initialValues.get(field)
            );
            if (submitBtn) {
                submitBtn.disabled = !isDirty;
            }
        };

        updateState();
        fields.forEach((field) => {
            field.addEventListener("input", updateState);
            field.addEventListener("change", updateState);
        });
    }

    const normalizeConfirm = (value) => (value || "").trim().toLowerCase();

    const editModalEl = document.getElementById("documentEditUnlockModal");
    const editInput = document.getElementById("doc-edit-confirm-input");
    const editConfirmBtn = document.getElementById("doc-edit-confirm-btn");
    const editFields = document.querySelectorAll("[data-doc-edit]");
    const editSaveBtn = document.getElementById("doc-edit-save-btn");
    const editConfirmHidden = document.getElementById("doc-edit-confirm-text");
    const editAccordionToggle = document.getElementById("doc-edit-accordion-toggle");
    const editCollapse = document.getElementById("collapse-edit");

    if (editInput && editConfirmBtn && editModalEl) {
        const expected = normalizeConfirm(editInput.dataset.expected || "");
        const toggleEditConfirm = () => {
            const matches = normalizeConfirm(editInput.value) === expected && expected;
            editConfirmBtn.disabled = !matches;
        };
        editInput.addEventListener("input", toggleEditConfirm);
        editModalEl.addEventListener("show.bs.modal", () => {
            editInput.value = "";
            editConfirmBtn.disabled = true;
        });
        editConfirmBtn.addEventListener("click", () => {
            editFields.forEach((field) => field.removeAttribute("disabled"));
            if (editSaveBtn) {
                editSaveBtn.removeAttribute("disabled");
            }
            if (editConfirmHidden) {
                editConfirmHidden.value = editInput.dataset.expected || "";
            }
            if (editAccordionToggle) {
                editAccordionToggle.removeAttribute("disabled");
                editAccordionToggle.setAttribute("aria-disabled", "false");
            }
            if (editCollapse) {
                if (window.bootstrap) {
                    const collapse = bootstrap.Collapse.getOrCreateInstance
                        ? bootstrap.Collapse.getOrCreateInstance(editCollapse, { toggle: false })
                        : new bootstrap.Collapse(editCollapse, { toggle: false });
                    collapse.show();
                } else {
                    editCollapse.classList.add("show");
                }
                editCollapse.scrollIntoView({ behavior: "smooth", block: "start" });
            }
            if (window.bootstrap) {
                const modal = bootstrap.Modal.getInstance(editModalEl);
                modal?.hide();
            }
        });
    }

    const deleteInput = document.getElementById("doc-delete-confirm-input");
    const deleteConfirmBtn = document.getElementById("doc-delete-confirm-btn");
    if (deleteInput && deleteConfirmBtn) {
        const expected = normalizeConfirm(deleteInput.dataset.expected || "");
        const toggleDelete = () => {
            const matches = normalizeConfirm(deleteInput.value) === expected && expected;
            deleteConfirmBtn.disabled = !matches;
        };
        deleteInput.addEventListener("input", toggleDelete);
        const deleteModalEl = document.getElementById("documentDeleteModal");
        deleteModalEl?.addEventListener("show.bs.modal", () => {
            deleteInput.value = "";
            deleteConfirmBtn.disabled = true;
        });
    }
});
