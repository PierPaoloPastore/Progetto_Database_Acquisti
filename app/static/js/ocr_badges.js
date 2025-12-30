window.OcrBadge = {
    apply(input, confidence = 0, labelText = "OCR") {
        if (!input) return;
        const targetId = input.getAttribute("id");
        const label = targetId ? document.querySelector(`label[for="${targetId}"]`) : null;
        const text = `${labelText} ${Math.round((confidence || 0) * 100)}%`;

        const badge = document.createElement("span");
        badge.className = "ocr-badge";
        if (confidence < 0.6) {
            badge.classList.add("ocr-badge-low");
        }
        badge.textContent = text;
        badge.setAttribute("data-ocr-badge", "true");

        if (label) {
            const existing = label.querySelector("[data-ocr-badge]");
            if (existing) {
                existing.remove();
            }
            label.appendChild(badge);
        } else {
            const existing = input.parentElement?.querySelector("[data-ocr-badge]");
            if (existing) {
                existing.remove();
            }
            input.insertAdjacentElement("afterend", badge);
        }

        input.classList.add("ocr-filled");
    }
};
