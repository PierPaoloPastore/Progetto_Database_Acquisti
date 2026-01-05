(function () {
    const DEFAULT_MAX_PAGES = 3;
    const DEFAULT_MAX_SIZE = 10 * 1024 * 1024;

    const normalizeList = (values) => {
        const seen = new Set();
        const output = [];
        values.forEach((value) => {
            if (!value) return;
            const normalized = String(value).trim().replace(/\s+/g, " ");
            if (!normalized) return;
            const hasDigit = /\d/.test(normalized);
            if (normalized.length < 3 && !(hasDigit && normalized.length >= 2)) return;
            const key = normalized.toLowerCase();
            if (seen.has(key)) return;
            seen.add(key);
            output.push({ raw: normalized, lower: key });
        });
        return output;
    };

    const buildAmountVariants = (rawValue) => {
        if (!rawValue) return [];
        const cleaned = String(rawValue).trim();
        if (!cleaned) return [];

        const stripped = cleaned.replace(/\s+/g, "");
        const numericToken = stripped.replace(/[^0-9.,]/g, "");

        const variants = new Set();
        if (numericToken) {
            variants.add(numericToken);
        }
        variants.add(stripped);
        variants.add(cleaned);

        let parsed = null;
        if (numericToken.includes(",") && numericToken.includes(".")) {
            parsed = parseFloat(numericToken.replace(/\./g, "").replace(",", "."));
        } else if (numericToken.includes(",")) {
            parsed = parseFloat(numericToken.replace(",", "."));
        } else if (numericToken) {
            parsed = parseFloat(numericToken);
        }

        if (!Number.isNaN(parsed) && parsed !== null) {
            variants.add(parsed.toFixed(2));
            variants.add(parsed.toFixed(2).replace(".", ","));
            variants.add(parsed.toFixed(0));
            const itFormat = new Intl.NumberFormat("it-IT", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }).format(parsed);
            const enFormat = new Intl.NumberFormat("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
            }).format(parsed);
            variants.add(itFormat);
            variants.add(enFormat);
        }

        return Array.from(variants);
    };

    const init = (options) => {
        const fileInput = options.fileInput;
        const viewer = options.viewer;
        const placeholder = options.placeholder;
        const status = options.status;
        const maxPages = options.maxPages || DEFAULT_MAX_PAGES;
        const maxSize = options.maxSize || DEFAULT_MAX_SIZE;
        const getHighlights = options.getHighlights;
        const watch = options.watch || [];

        if (!fileInput || !viewer || !placeholder) {
            return null;
        }

        if (!window.pdfjsLib) {
            if (status) {
                status.textContent = "PDF preview non disponibile.";
                status.classList.add("is-visible");
            }
            return null;
        }

        const workerSrc = options.workerSrc || window.PDFJS_WORKER_SRC;
        if (workerSrc) {
            window.pdfjsLib.GlobalWorkerOptions.workerSrc = workerSrc;
        }

        const state = {
            textLayers: [],
            hasText: false,
            loaded: false,
        };

        const clearViewer = () => {
            viewer.innerHTML = "";
            viewer.classList.add("is-hidden");
            state.textLayers = [];
            state.hasText = false;
            state.loaded = false;
            if (status) {
                status.textContent = "";
                status.classList.remove("is-visible");
            }
        };

        const setStatus = (message) => {
            if (!status) return;
            if (!message) {
                status.textContent = "";
                status.classList.remove("is-visible");
                return;
            }
            status.textContent = message;
            status.classList.add("is-visible");
        };

        const applyHighlights = () => {
            if (!state.loaded) return;
            const values = normalizeList(getHighlights ? getHighlights() : []);
            state.textLayers.forEach((layer) => {
                const spans = layer.querySelectorAll("span");
                spans.forEach((span) => span.classList.remove("pdf-highlight"));
                if (!values.length) return;
                spans.forEach((span) => {
                    const text = (span.textContent || "").toLowerCase();
                    if (!text) return;
                    const matched = values.some((val) => text.includes(val.lower));
                    if (matched) {
                        span.classList.add("pdf-highlight");
                    }
                });
            });
        };

        const renderPdf = async (file) => {
            const data = await file.arrayBuffer();
            const pdf = await window.pdfjsLib.getDocument({ data }).promise;
            const pagesToRender = Math.min(pdf.numPages, maxPages);
            const textLayers = [];
            let hasText = false;

            viewer.innerHTML = "";
            viewer.classList.remove("is-hidden");

            for (let pageNumber = 1; pageNumber <= pagesToRender; pageNumber += 1) {
                const page = await pdf.getPage(pageNumber);
                const viewport = page.getViewport({ scale: 1.2 });
                const pixelRatio = window.devicePixelRatio || 1;

                const pageWrapper = document.createElement("div");
                pageWrapper.className = "pdf-page";

                const canvas = document.createElement("canvas");
                const context = canvas.getContext("2d");
                canvas.width = Math.floor(viewport.width * pixelRatio);
                canvas.height = Math.floor(viewport.height * pixelRatio);
                canvas.style.width = `${Math.floor(viewport.width)}px`;
                canvas.style.height = `${Math.floor(viewport.height)}px`;

                pageWrapper.style.width = canvas.style.width;
                pageWrapper.style.height = canvas.style.height;

                const textLayer = document.createElement("div");
                textLayer.className = "textLayer";

                pageWrapper.appendChild(canvas);
                pageWrapper.appendChild(textLayer);
                viewer.appendChild(pageWrapper);

                const renderContext = {
                    canvasContext: context,
                    viewport,
                    transform: [pixelRatio, 0, 0, pixelRatio, 0, 0],
                };
                await page.render(renderContext).promise;

                const textContent = await page.getTextContent();
                if (textContent.items && textContent.items.length > 0) {
                    hasText = true;
                }

                await window.pdfjsLib.renderTextLayer({
                    textContent,
                    container: textLayer,
                    viewport,
                    textDivs: [],
                }).promise;

                textLayers.push(textLayer);
            }

            state.textLayers = textLayers;
            state.hasText = hasText;
            state.loaded = true;

            if (!hasText) {
                setStatus("Testo non rilevabile (PDF scannerizzato).");
            } else {
                setStatus("");
            }

            applyHighlights();
        };

        const handleFileChange = async () => {
            const file = fileInput.files && fileInput.files[0];
            if (!file) {
                clearViewer();
                placeholder.classList.remove("d-none");
                return;
            }

            if (file.type !== "application/pdf") {
                alert("Solo file PDF sono consentiti.");
                fileInput.value = "";
                clearViewer();
                placeholder.classList.remove("d-none");
                return;
            }

            if (file.size > maxSize) {
                alert("File troppo grande. Massimo 10MB consentito.");
                fileInput.value = "";
                clearViewer();
                placeholder.classList.remove("d-none");
                return;
            }

            placeholder.classList.add("d-none");
            setStatus("Rendering PDF...");

            try {
                await renderPdf(file);
            } catch (error) {
                clearViewer();
                placeholder.classList.remove("d-none");
                setStatus("Errore durante la preview PDF.");
            }
        };

        fileInput.addEventListener("change", () => {
            handleFileChange();
        });

        watch.forEach((el) => {
            if (!el) return;
            el.addEventListener("change", applyHighlights);
            el.addEventListener("keyup", applyHighlights);
        });

        return {
            refreshHighlights: applyHighlights,
        };
    };

    window.PdfUploadPreview = {
        init,
        buildAmountVariants,
    };
})();
