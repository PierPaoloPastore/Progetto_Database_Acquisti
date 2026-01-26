document.addEventListener("DOMContentLoaded", () => {
    const frame = document.getElementById("xsl-preview-frame");
    const selector = document.getElementById("xsl-style-selector");
    const openPreviewBtn = document.getElementById("preview-open");
    if (selector && frame) {
        selector.addEventListener("change", () => {
            const style = selector.value || "ordinaria";
            const url = new URL(frame.src, window.location.origin);
            url.searchParams.set("style", style);
            url.searchParams.set("highlight", "1");
            frame.src = url.toString();
            if (openPreviewBtn) {
                openPreviewBtn.href = url.toString();
            }
        });
        if (openPreviewBtn) {
            openPreviewBtn.href = frame.src;
        }
    }

    const entitySelect = document.getElementById("legal-entity-id");
    const entityName = document.getElementById("legal-entity-name");
    if (entitySelect && entityName) {
        entitySelect.addEventListener("change", () => {
            const selected = entitySelect.options[entitySelect.selectedIndex];
            if (!selected || !selected.value) return;
            entityName.value = (selected.textContent || "").trim();
            entityName.dispatchEvent(new Event("input", { bubbles: true }));
        });
    }

    const split = document.querySelector(".review-split");
    const splitter = document.querySelector(".review-splitter");
    if (split && splitter) {
        const storageKey = "review_split_width_pct";
        const minPct = 0.3;
        const maxPct = 0.7;
        const snapPoints = [0.3, 0.5, 0.7];
        const snapThreshold = 0.03;
        let dragging = false;
        let activePointerId = null;

        const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
        const snap = (value) => {
            for (const point of snapPoints) {
                if (Math.abs(value - point) <= snapThreshold) {
                    return point;
                }
            }
            return value;
        };
        const applyWidth = (pct, persist) => {
            const clamped = clamp(pct, minPct, maxPct);
            split.style.setProperty("--review-viewer-width", `${Math.round(clamped * 100)}%`);
            if (persist) {
                localStorage.setItem(storageKey, String(Math.round(clamped * 100)));
            }
        };

        const saved = localStorage.getItem(storageKey);
        if (saved) {
            const savedPct = Number(saved) / 100;
            if (!Number.isNaN(savedPct)) {
                applyWidth(savedPct, false);
            }
        }

        const updateWidth = (clientX) => {
            const rect = split.getBoundingClientRect();
            const rightWidth = rect.right - clientX;
            const pct = rightWidth / rect.width;
            const snapped = snap(pct);
            applyWidth(snapped, false);
        };

        splitter.addEventListener("pointerdown", (event) => {
            dragging = true;
            activePointerId = event.pointerId;
            document.body.classList.add("review-resizing");
            splitter.setPointerCapture(event.pointerId);
            updateWidth(event.clientX);
            event.preventDefault();
        });

        splitter.addEventListener("pointermove", (event) => {
            if (!dragging || event.pointerId !== activePointerId) return;
            updateWidth(event.clientX);
        });

        const stopDragging = (event) => {
            if (!dragging || event.pointerId !== activePointerId) return;
            dragging = false;
            activePointerId = null;
            document.body.classList.remove("review-resizing");
            splitter.releasePointerCapture(event.pointerId);
            const current = split.style.getPropertyValue("--review-viewer-width");
            const value = Number(current.replace("%", "")) / 100;
            if (!Number.isNaN(value)) {
                applyWidth(value, true);
            }
        };

        splitter.addEventListener("pointerup", stopDragging);
        splitter.addEventListener("pointercancel", stopDragging);
        splitter.addEventListener("dblclick", () => applyWidth(0.5, true));
    }

    const toolbar = document.getElementById("preview-toolbar");
    if (toolbar && frame) {
        let zoomLevel = 1;
        const clampZoom = (value) => Math.min(1.5, Math.max(0.6, value));
        const applyZoom = () => {
            try {
                const docEl = frame.contentDocument?.documentElement;
                const body = frame.contentDocument?.body;
                if (docEl) {
                    docEl.style.zoom = String(zoomLevel);
                }
                if (body) {
                    body.style.zoom = String(zoomLevel);
                }
            } catch (error) {
                // Cross-origin or sandboxed preview: ignore zoom.
            }
        };
        frame.addEventListener("load", applyZoom);

        toolbar.addEventListener("click", (event) => {
            const button = event.target.closest("button[data-action]");
            if (!button) return;
            const action = button.dataset.action;
            if (action === "zoom-in") {
                zoomLevel = clampZoom(zoomLevel + 0.1);
                applyZoom();
            } else if (action === "zoom-out") {
                zoomLevel = clampZoom(zoomLevel - 0.1);
                applyZoom();
            } else if (action === "fit-width") {
                zoomLevel = 1;
                applyZoom();
            }
        });
    }

    const discardModalEl = document.getElementById("discardModal");
    const discardModal = discardModalEl && window.bootstrap
        ? new bootstrap.Modal(discardModalEl)
        : null;
    const discardTrigger = document.getElementById("discard-trigger");
    if (discardTrigger && discardModal) {
        discardTrigger.addEventListener("click", () => discardModal.show());
    }

    const reasonRadios = Array.from(document.querySelectorAll("input[name='discard_reason']"));
    const reasonOther = document.getElementById("discard-reason-other");
    const confirmDiscardBtn = document.getElementById("discard-confirm");
    const updateDiscardState = () => {
        const selected = reasonRadios.find((radio) => radio.checked);
        const isOther = selected && selected.value === "other";
        if (reasonOther) {
            reasonOther.closest(".review-discard-note")?.classList.toggle("d-none", !isOther);
            if (!isOther) {
                reasonOther.value = "";
            }
        }
        if (confirmDiscardBtn) {
            confirmDiscardBtn.disabled = !selected;
        }
    };
    if (reasonRadios.length) {
        reasonRadios.forEach((radio) => radio.addEventListener("change", updateDiscardState));
        updateDiscardState();
    }

    if (discardModalEl) {
        discardModalEl.addEventListener("show.bs.modal", () => {
            reasonRadios.forEach((radio) => (radio.checked = false));
            if (confirmDiscardBtn) {
                confirmDiscardBtn.disabled = true;
            }
            if (reasonOther) {
                reasonOther.value = "";
                reasonOther.closest(".review-discard-note")?.classList.add("d-none");
            }
        });
    }

    const isTypingTarget = (target) => {
        if (!target) return false;
        if (target.isContentEditable) return true;
        const tag = target.tagName ? target.tagName.toLowerCase() : "";
        return tag === "input" || tag === "textarea" || tag === "select";
    };

    const confirmBtn = document.getElementById("confirm-next");
    const saveBtn = document.getElementById("save-stay");
    document.addEventListener("keydown", (event) => {
        if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
        if (isTypingTarget(event.target)) return;
        const modalOpen = document.querySelector(".modal.show");
        if (event.key === "Escape" && modalOpen && window.bootstrap) {
            const openModal = bootstrap.Modal.getInstance(modalOpen);
            if (openModal) {
                openModal.hide();
                event.preventDefault();
            }
            return;
        }
        if (modalOpen) return;
        if (event.key === "Enter" && confirmBtn) {
            confirmBtn.click();
            event.preventDefault();
        } else if ((event.key === "s" || event.key === "S") && discardModal) {
            discardModal.show();
            event.preventDefault();
        } else if ((event.key === "r" || event.key === "R") && saveBtn) {
            saveBtn.click();
            event.preventDefault();
        }
    });

    const noteFields = document.querySelectorAll(".js-autoresize");
    const autoResize = (field) => {
        field.style.height = "auto";
        field.style.height = `${field.scrollHeight}px`;
    };
    noteFields.forEach((field) => {
        autoResize(field);
        field.addEventListener("input", () => autoResize(field));
    });

    const normalizeNumber = (value) => {
        if (value === null || value === undefined) return null;
        const cleaned = String(value)
            .replace(/\s+/g, "")
            .replace("€", "")
            .replace(",", ".")
            .replace(/[^0-9.-]/g, "");
        if (!cleaned) return null;
        const parsed = Number(cleaned);
        return Number.isNaN(parsed) ? null : parsed;
    };
    const normalizeDate = (value) => {
        if (!value) return "";
        return String(value).trim();
    };
    const normalizeText = (value) => (value || "").toString().trim().toLowerCase();
    const formatNumber = (value) => {
        const parsed = normalizeNumber(value);
        if (parsed === null) return "";
        return parsed.toFixed(2);
    };

    const compareFields = document.querySelectorAll(".js-compare-field");
    const updateComparison = (field) => {
        const type = field.dataset.compareType || "text";
        const expectedRaw = field.dataset.expected || "";
        const expectedDisplay = field.dataset.expectedDisplay || "";
        let matches = false;
        let displayValue = expectedDisplay;

        if (type === "number") {
            const expectedValue = normalizeNumber(expectedRaw);
            const currentValue = normalizeNumber(field.value);
            if (expectedValue === null && currentValue === null) {
                matches = true;
            } else if (expectedValue !== null && currentValue !== null) {
                matches = Math.abs(expectedValue - currentValue) < 0.005;
            }
            if (!displayValue) {
                displayValue = expectedValue === null ? "" : formatNumber(expectedValue);
            }
        } else if (type === "date") {
            const expectedValue = normalizeDate(expectedRaw);
            const currentValue = normalizeDate(field.value);
            matches = expectedValue === currentValue;
            if (!displayValue) {
                displayValue = expectedValue;
            }
        } else if (type === "select") {
            const expectedValue = expectedRaw;
            matches = String(field.value || "") === String(expectedValue || "");
            if (!displayValue && expectedValue) {
                const option = field.querySelector(`option[value='${expectedValue}']`);
                displayValue = option ? option.textContent.trim() : expectedValue;
            }
        } else {
            matches = normalizeText(expectedRaw) === normalizeText(field.value);
            if (!displayValue) {
                displayValue = expectedRaw;
            }
        }

        field.classList.toggle("is-mismatch", !matches && expectedRaw);
        field.classList.toggle("is-match", matches && expectedRaw);

        const group = field.closest(".js-compare-group");
        if (!group) return;
        const indicator = group.querySelector(".field-indicator");
        const expectedEl = group.querySelector(".field-expected");
        if (indicator) {
            indicator.classList.toggle("is-visible", matches && expectedRaw);
        }
        if (expectedEl) {
            if (!matches && expectedRaw) {
                expectedEl.textContent = displayValue ? `Nel documento: ${displayValue}` : "";
                expectedEl.classList.add("is-visible");
            } else {
                expectedEl.textContent = "";
                expectedEl.classList.remove("is-visible");
            }
        }
    };

    compareFields.forEach((field) => {
        updateComparison(field);
        field.addEventListener("input", () => updateComparison(field));
        field.addEventListener("change", () => updateComparison(field));
    });

    const numberFields = document.querySelectorAll(".js-format-decimal");
    numberFields.forEach((field) => {
        const applyFormat = () => {
            if (!field.value) return;
            field.value = formatNumber(field.value);
            updateComparison(field);
        };
        applyFormat();
        field.addEventListener("blur", applyFormat);
    });
});
