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
});
