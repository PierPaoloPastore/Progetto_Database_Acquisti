document.addEventListener("DOMContentLoaded", () => {
    const refreshSelect2 = (select) => {
        if (!select || !window.jQuery) return;
        const $el = window.jQuery(select);
        if ($el.data("select2")) {
            $el.trigger("change.select2");
        }
    };

    const frame = document.getElementById("xsl-preview-frame");
    const selector = document.getElementById("xsl-style-selector");
    const openPreviewBtn = document.getElementById("preview-open");
    const highlightToggleBtn = document.getElementById("preview-highlight-toggle");
    let highlightEnabled = false;
    const buildPreviewUrl = () => {
        if (!frame) return null;
        const url = new URL(frame.src, window.location.origin);
        const style = selector ? (selector.value || "ordinaria") : (url.searchParams.get("style") || "ordinaria");
        url.searchParams.set("style", style);
        if (highlightEnabled) {
            url.searchParams.set("highlight", "1");
        } else {
            url.searchParams.delete("highlight");
        }
        return url;
    };
    const updateHighlightToggle = () => {
        if (!highlightToggleBtn) return;
        highlightToggleBtn.textContent = highlightEnabled ? "Highlight on" : "Highlight off";
        highlightToggleBtn.classList.toggle("btn-outline-warning", highlightEnabled);
        highlightToggleBtn.classList.toggle("btn-outline-secondary", !highlightEnabled);
        highlightToggleBtn.setAttribute("aria-pressed", highlightEnabled ? "true" : "false");
    };
    const refreshPreview = () => {
        const url = buildPreviewUrl();
        if (!url) return;
        frame.src = url.toString();
        if (openPreviewBtn) {
            openPreviewBtn.href = url.toString();
        }
        updateHighlightToggle();
    };
    if (selector && frame) {
        selector.addEventListener("change", () => {
            refreshPreview();
        });
        if (openPreviewBtn) {
            openPreviewBtn.href = frame.src;
        }
    }
    if (highlightToggleBtn && frame) {
        highlightToggleBtn.addEventListener("click", () => {
            highlightEnabled = !highlightEnabled;
            refreshPreview();
        });
        updateHighlightToggle();
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

    const instantToggle = document.getElementById("instant-payment-toggle");
    const ibanSelect = document.getElementById("instant-payment-iban");
    const ibanEmpty = document.getElementById("instant-iban-empty");
    const instantHidden = document.getElementById("instant-payment-hidden");
    const ibanHidden = document.getElementById("instant-payment-iban-hidden");
    const ibanAccountsUrl = ibanSelect ? (ibanSelect.dataset.accountsUrl || "") : "";
    const ibanCache = new Map();
    let instantAvailable = instantToggle ? !instantToggle.disabled : false;

    const updateIbanEnabled = () => {
        if (!ibanSelect) return;
        const shouldDisable = !instantAvailable || (instantToggle && !instantToggle.checked);
        ibanSelect.disabled = shouldDisable;
        refreshSelect2(ibanSelect);
    };

    const syncHidden = () => {
        if (instantHidden) {
            instantHidden.value = instantToggle && instantToggle.checked ? "1" : "";
        }
        if (ibanHidden && ibanSelect) {
            ibanHidden.value = ibanSelect.value || "";
        }
    };

    const clearIbanOptions = () => {
        if (!ibanSelect) return;
        Array.from(ibanSelect.querySelectorAll("option[data-dynamic-account='1']")).forEach((option) => option.remove());
        ibanSelect.value = "";
    };

    const setIbanEmptyState = (message, visible) => {
        if (!ibanEmpty) return;
        ibanEmpty.textContent = message;
        ibanEmpty.hidden = !visible;
        ibanEmpty.disabled = !visible;
    };

    const populateIbanOptions = (accounts) => {
        if (!ibanSelect) return;
        const currentValue = ibanSelect.value || "";
        clearIbanOptions();
        accounts.forEach((account) => {
            const option = document.createElement("option");
            option.value = account.iban;
            option.textContent = `${account.name} - ${account.iban}`;
            option.setAttribute("data-legal-entity-id", String(account.legal_entity_id || ""));
            option.setAttribute("data-dynamic-account", "1");
            ibanSelect.appendChild(option);
        });
        if (accounts.some((account) => account.iban === currentValue)) {
            ibanSelect.value = currentValue;
        }
        const entityId = entitySelect ? (entitySelect.value || "") : "";
        if (!entityId) {
            setIbanEmptyState("Seleziona prima un intestatario.", true);
        } else if (!accounts.length) {
            setIbanEmptyState("Nessun conto disponibile", true);
        } else {
            setIbanEmptyState("Nessun conto disponibile", false);
        }
        if (window.initSelect2Controls) {
            window.initSelect2Controls(ibanSelect.parentElement || ibanSelect);
        } else {
            refreshSelect2(ibanSelect);
        }
        syncHidden();
    };

    const ensureIbanOptions = async ({ forceReload = false } = {}) => {
        if (!ibanSelect || !entitySelect || !ibanAccountsUrl) return;
        const entityId = entitySelect.value || "";
        if (!entityId) {
            populateIbanOptions([]);
            return;
        }
        if (!forceReload && ibanCache.has(entityId)) {
            populateIbanOptions(ibanCache.get(entityId) || []);
            return;
        }

        setIbanEmptyState("Carico conti...", true);
        refreshSelect2(ibanSelect);

        try {
            const url = new URL(ibanAccountsUrl, window.location.origin);
            url.searchParams.set("legal_entity_id", entityId);
            const response = await fetch(url.toString(), {
                method: "GET",
                headers: { "Accept": "application/json" },
                credentials: "same-origin",
            });
            const data = await response.json().catch(() => null);
            if (!response.ok || !data?.ok) {
                throw new Error(data?.message || "Errore nel caricamento dei conti.");
            }
            ibanCache.set(entityId, Array.isArray(data.accounts) ? data.accounts : []);
            populateIbanOptions(ibanCache.get(entityId) || []);
        } catch (error) {
            console.error(error);
            populateIbanOptions([]);
            setIbanEmptyState("Errore caricamento conti", true);
        }
    };

    if (instantToggle) {
        instantToggle.addEventListener("change", async () => {
            if (instantToggle.checked && instantAvailable) {
                await ensureIbanOptions();
            }
            updateIbanEnabled();
            syncHidden();
        });
    }
    if (ibanSelect) {
        ibanSelect.addEventListener("change", syncHidden);
    }
    if (entitySelect && ibanSelect) {
        entitySelect.addEventListener("change", async () => {
            clearIbanOptions();
            if (instantAvailable && instantToggle && instantToggle.checked) {
                await ensureIbanOptions();
            } else {
                populateIbanOptions([]);
            }
            updateIbanEnabled();
        });
    }
    updateIbanEnabled();
    populateIbanOptions([]);
    syncHidden();

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
        let fitMode = true;
        const zoomLabel = document.getElementById("preview-zoom-label");
        const zoomMode = document.getElementById("preview-zoom-mode");
        const clampZoom = (value) => Math.min(1.5, Math.max(0.6, value));
        const updateZoomLabel = () => {
            if (zoomLabel) {
                zoomLabel.textContent = `${Math.round(zoomLevel * 100)}%`;
            }
            if (zoomMode) {
                zoomMode.textContent = fitMode ? "Adatta larghezza" : "Zoom manuale";
            }
        };
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
            updateZoomLabel();
        };
        frame.addEventListener("load", applyZoom);

        toolbar.addEventListener("click", (event) => {
            const button = event.target.closest("button[data-action]");
            if (!button) return;
            const action = button.dataset.action;
            if (action === "zoom-in") {
                fitMode = false;
                zoomLevel = clampZoom(zoomLevel + 0.1);
                applyZoom();
            } else if (action === "zoom-out") {
                fitMode = false;
                zoomLevel = clampZoom(zoomLevel - 0.1);
                applyZoom();
            } else if (action === "fit-width") {
                fitMode = true;
                zoomLevel = 1;
                applyZoom();
            }
        });

        updateZoomLabel();
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
        group.classList.toggle("is-mismatch", !matches && expectedRaw);
        group.classList.toggle("is-match", matches && expectedRaw);
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

    const applyAllCategoriesBtn = document.getElementById("category-apply-all-btn");
    const applyAllCategoriesSelect = document.getElementById("category-apply-all-select");
    const categoryLineSelects = document.querySelectorAll(".js-category-line-select");
    if (applyAllCategoriesBtn && applyAllCategoriesSelect && categoryLineSelects.length) {
        applyAllCategoriesBtn.addEventListener("click", () => {
            const targetValue = applyAllCategoriesSelect.value || "";
            if (!targetValue) return;
            categoryLineSelects.forEach((select) => {
                select.value = targetValue;
                select.dispatchEvent(new Event("change", { bubbles: true }));
                refreshSelect2(select);
            });
        });
    }

    const paymentMethodForm = document.querySelector("form[data-ajax='payment-method']");
    if (paymentMethodForm) {
        const feedback = document.querySelector("[data-payment-feedback]");
        const labelEl = document.querySelector("[data-payment-label]");
        const reasonEl = document.querySelector("[data-instant-reason]");
        const select = paymentMethodForm.querySelector("select[name='payment_method_code']");
        const submitBtn = paymentMethodForm.querySelector("button[type='submit']");

        const setFeedback = (message, ok) => {
            if (!feedback) return;
            feedback.textContent = message || "";
            feedback.classList.remove("d-none", "text-danger", "text-success", "text-muted");
            feedback.classList.add(ok ? "text-success" : "text-danger");
        };

        paymentMethodForm.addEventListener("submit", async (event) => {
            if (!select) return;
            event.preventDefault();
            const ajaxUrl = paymentMethodForm.dataset.ajaxUrl || paymentMethodForm.getAttribute("action");
            if (!ajaxUrl) {
                setFeedback("URL di aggiornamento mancante.", false);
                return;
            }
            if (submitBtn) {
                submitBtn.disabled = true;
            }
            if (feedback) {
                feedback.textContent = "Aggiorno metodo...";
                feedback.classList.remove("text-danger", "text-success", "d-none");
                feedback.classList.add("text-muted");
            }

            const formData = new FormData(paymentMethodForm);

            try {
                const response = await fetch(ajaxUrl, {
                    method: "POST",
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/json",
                    },
                    credentials: "same-origin",
                    body: formData,
                });

                const contentType = response.headers.get("content-type") || "";
                let data = null;
                let textPayload = "";
                if (contentType.includes("application/json")) {
                    data = await response.json().catch(() => null);
                } else {
                    textPayload = await response.text().catch(() => "");
                }

                if (!response.ok || (!data && !textPayload)) {
                    throw new Error(data?.message || textPayload || "Errore durante l'aggiornamento.");
                }

                setFeedback(data.message || "Metodo aggiornato.", true);

                if (labelEl) {
                    if (Array.isArray(data.labels) && data.labels.length) {
                        labelEl.textContent = `Metodo attuale: ${data.labels.join(", ")}`;
                    } else {
                        const selectedText = select.options[select.selectedIndex]?.textContent?.trim() || "-";
                        labelEl.textContent = `Metodo attuale: ${selectedText}`;
                    }
                }

                if (instantToggle) {
                    instantAvailable = Boolean(data.instant_allowed);
                    instantToggle.disabled = !data.instant_allowed;
                    if (!data.instant_allowed) {
                        instantToggle.checked = false;
                        clearIbanOptions();
                        populateIbanOptions([]);
                    }
                    instantToggle.dispatchEvent(new Event("change", { bubbles: true }));
                }

                if (reasonEl) {
                    if (data.instant_reason) {
                        reasonEl.textContent = data.instant_reason;
                        reasonEl.classList.remove("d-none");
                    } else {
                        reasonEl.textContent = "";
                        reasonEl.classList.add("d-none");
                    }
                }
            } catch (error) {
                const message = error?.message || "Errore durante l'aggiornamento.";
                setFeedback(message, false);
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                }
            }
        });
    }
});
