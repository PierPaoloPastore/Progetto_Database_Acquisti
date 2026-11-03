(() => {
    const form = document.querySelector('.reports-filters');
    if (!form) return;
    const start = form.elements.date_from;
    const end = form.elements.date_to;
    const picker = form.querySelector('.category-picker');
    const summary = document.getElementById('categories-summary');
    const search = document.getElementById('category-search');
    const status = form.querySelector('[data-report-status]');
    const refresh = form.querySelector('[data-report-refresh]');
    const results = document.querySelector('[data-report-results]');
    const checkboxes = [...picker.querySelectorAll('input[type="checkbox"]')];
    let timer;
    let controller;

    function validatePeriod() {
        start.required = Boolean(end.value);
        end.required = Boolean(start.value);
        end.min = start.value;
    }

    function updateSummary() {
        const selected = checkboxes.filter(input => input.checked);
        summary.textContent = selected.length === 1
            ? selected[0].closest('label').textContent.trim()
            : selected.length ? `${selected.length} selezionate` : 'Tutte le categorie';
        summary.title = selected.map(input => input.closest('label').textContent.trim()).join(', ');
    }

    search.addEventListener('input', () => {
        const term = search.value.trim().toLocaleLowerCase('it');
        const options = [...picker.querySelectorAll('.category-picker-option')];
        options.forEach(option => {
            option.hidden = !option.textContent.toLocaleLowerCase('it').includes(term);
        });
        picker.querySelector('[data-category-no-match]').hidden = options.some(option => !option.hidden);
    });
    picker.querySelector('[data-clear-categories]').addEventListener('click', () => {
        checkboxes.forEach(input => { input.checked = false; });
        form.dispatchEvent(new Event('change', { bubbles: true }));
    });
    document.addEventListener('click', event => {
        if (!picker.contains(event.target)) picker.open = false;
    });
    picker.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            picker.open = false;
            picker.querySelector('summary').focus();
        }
        if (event.key === 'Enter' && event.target === search) event.preventDefault();
    });
    picker.addEventListener('focusout', event => {
        if (!picker.contains(event.relatedTarget)) picker.open = false;
    });

    function cancelPending() {
        clearTimeout(timer);
        controller?.abort();
        controller = null;
        results.removeAttribute('aria-busy');
    }

    async function updateReport() {
        if (!form.checkValidity()) return;
        const requestController = new AbortController();
        controller = requestController;
        const url = new URL(form.action);
        for (const [key, value] of new FormData(form)) {
            if (value) url.searchParams.append(key, value);
        }
        status.textContent = 'Aggiornamento in corso…';
        results.setAttribute('aria-busy', 'true');
        refresh.hidden = true;
        try {
            const response = await fetch(url, { signal: requestController.signal });
            if (!response.ok) throw new Error('Report non disponibile');
            const html = new DOMParser().parseFromString(await response.text(), 'text/html');
            // Una risposta superata non deve sostituire i filtri più recenti.
            if (controller !== requestController) return;
            const nextResults = html.querySelector('[data-report-results]');
            const nextHeading = html.querySelector('[data-report-heading]');
            const nextForm = html.querySelector('.reports-filters');
            if (!nextResults || !nextHeading || !nextForm) throw new Error('Risposta non valida');
            const openCategories = new Set([...results.querySelectorAll('.category-entity-split[open]')]
                .map(details => details.dataset.categoryId));
            nextResults.querySelectorAll('.category-entity-split').forEach(details => {
                details.open = openCategories.has(details.dataset.categoryId);
            });
            if (results.querySelector('.category-other-details[open]')) {
                const other = nextResults.querySelector('.category-other-details');
                if (other) other.open = true;
            }
            results.replaceChildren(...nextResults.childNodes);
            document.querySelector('[data-report-heading]').replaceWith(nextHeading);
            for (const name of ['year', 'type', 'legal_entity_id']) {
                const current = form.elements[name];
                const next = nextForm.elements[name];
                const value = next.value;
                current.replaceChildren(...next.childNodes);
                current.value = value;
            }
            history.replaceState(null, '', url);
            status.textContent = 'Filtri applicati automaticamente';
        } catch (error) {
            if (error.name === 'AbortError' || controller !== requestController) return;
            status.textContent = 'Aggiornamento non riuscito. Sono ancora visibili i risultati precedenti. Premi Riprova.';
            refresh.lastChild.textContent = ' Riprova';
            refresh.hidden = false;
        } finally {
            if (controller === requestController) {
                results.removeAttribute('aria-busy');
                controller = null;
            }
        }
    }

    function scheduleUpdate() {
        cancelPending();
        validatePeriod();
        updateSummary();
        if (!form.checkValidity()) {
            status.textContent = 'Completa un intervallo di date valido per aggiornare il report.';
            return;
        }
        status.textContent = 'Applicazione dei filtri…';
        timer = setTimeout(updateReport, 450);
    }

    [start, end].forEach(input => input.addEventListener('input', () => {
        cancelPending();
        validatePeriod();
        status.textContent = 'Completa le date per aggiornare il report.';
    }));
    form.addEventListener('change', event => {
        if (event.target === form.elements.year) {
            start.value = '';
            end.value = '';
        }
        if (event.target !== search) scheduleUpdate();
    });
    form.addEventListener('submit', event => {
        if (event.submitter?.value === 'csv') return;
        event.preventDefault();
        cancelPending();
        validatePeriod();
        if (form.reportValidity()) updateReport();
    });
    validatePeriod();
    updateSummary();
    refresh.hidden = true;
    status.textContent = 'I filtri si applicano automaticamente';
})();
