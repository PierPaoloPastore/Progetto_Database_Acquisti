(() => {
    const form = document.querySelector('.reports-filters');
    if (!form) return;
    const start = form.elements.date_from;
    const end = form.elements.date_to;
    const categories = [...form.querySelectorAll('input[name="category_id"]')];
    const search = document.getElementById('category-search');
    const summary = document.getElementById('categories-summary');
    const status = form.querySelector('[data-report-status]');

    function validatePeriod() {
        start.required = Boolean(end.value);
        end.required = Boolean(start.value);
        end.min = start.value;
    }

    function updateSummary() {
        const selected = categories.filter(input => input.checked);
        summary.textContent = selected.length === 1 ? selected[0].parentElement.textContent.trim()
            : selected.length ? `${selected.length} selezionate` : 'Tutte';
        summary.title = selected.map(input => input.parentElement.textContent.trim()).join(', ');
    }

    function markFiltersChanged() {
        validatePeriod();
        updateSummary();
        status.textContent = start.validity.valid && end.validity.valid
            ? 'Filtri modificati. Premi Aggiorna per applicarli.'
            : 'Completa un intervallo di date valido, poi premi Aggiorna.';
    }

    form.querySelector('[data-clear-categories]').addEventListener('click', () => {
        categories.forEach(input => { input.checked = false; });
        markFiltersChanged();
    });

    search.addEventListener('input', () => {
        const term = search.value.trim().toLocaleLowerCase('it');
        const options = [...form.querySelectorAll('.category-filter-option')];
        options.forEach(option => {
            option.hidden = !option.textContent.toLocaleLowerCase('it').includes(term);
        });
        form.querySelector('[data-category-no-match]').hidden = options.some(option => !option.hidden);
    });
    search.addEventListener('keydown', event => {
        if (event.key === 'Enter') event.preventDefault();
    });

    [start, end].forEach(input => input.addEventListener('input', markFiltersChanged));
    form.addEventListener('change', event => {
        if (event.target === search) return;
        if (event.target === form.elements.year) {
            start.value = '';
            end.value = '';
        }
        markFiltersChanged();
    });
    validatePeriod();
    updateSummary();
})();
