(() => {
    const form = document.querySelector('.reports-filters');
    if (!form) return;
    const start = form.elements.date_from;
    const end = form.elements.date_to;
    const picker = form.querySelector('.category-picker');
    const summary = document.getElementById('categories-summary');
    const search = document.getElementById('category-search');
    const status = form.querySelector('[data-report-status]');
    const checkboxes = [...picker.querySelectorAll('input[type="checkbox"]')];

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

    function markFiltersChanged() {
        validatePeriod();
        updateSummary();
        status.textContent = form.checkValidity()
            ? 'Filtri modificati. Premi Aggiorna per applicarli.'
            : 'Completa un intervallo di date valido, poi premi Aggiorna.';
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
        markFiltersChanged();
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

    [start, end].forEach(input => input.addEventListener('input', markFiltersChanged));
    form.addEventListener('change', event => {
        if (event.target === form.elements.year) {
            start.value = '';
            end.value = '';
        }
        if (event.target !== search) markFiltersChanged();
    });
    validatePeriod();
    updateSummary();
})();
