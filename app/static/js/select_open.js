document.addEventListener("click", (event) => {
    const label = event.target.closest("label[for]");
    if (label) {
        const targetId = label.getAttribute("for");
        if (targetId) {
            const select = document.getElementById(targetId);
            if (select && select.tagName === "SELECT") {
                select.focus();
                select.click();
                return;
            }
        }
    }

    const group = event.target.closest(".input-group, .form-floating, .select-click-area");
    if (!group) {
        return;
    }

    if (event.target.closest("select")) {
        return;
    }

    if (event.target.closest("input, textarea, button, a")) {
        return;
    }

    const select = group.querySelector("select");
    if (!select) {
        return;
    }

    select.focus();
    select.click();
});
