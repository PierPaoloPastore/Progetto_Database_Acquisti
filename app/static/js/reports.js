(() => {
    const form = document.querySelector('.reports-filters');
    if (!form) return;
    const start = form.elements.date_from;
    const end = form.elements.date_to;
    const categories = document.getElementById('report-categories');
    const summary = document.getElementById('categories-summary');
    const status = form.querySelector('[data-report-status]');

    function validatePeriod() {
        start.required = Boolean(end.value);
        end.required = Boolean(start.value);
        end.min = start.value;
    }

    function updateSummary() {
        const count = categories.selectedOptions.length;
        summary.textContent = count === 1 ? '1 selezionata'
            : count ? `${count} selezionate` : 'Nessuna selezione = tutte';
    }

    function markFiltersChanged() {
        validatePeriod();
        updateSummary();
        status.textContent = start.validity.valid && end.validity.valid
            ? 'Filtri modificati. Premi Aggiorna per applicarli.'
            : 'Completa un intervallo di date valido, poi premi Aggiorna.';
    }

    form.querySelector('[data-clear-categories]').addEventListener('click', () => {
        for (const option of categories.options) option.selected = false;
        markFiltersChanged();
    });

    [start, end].forEach(input => input.addEventListener('input', markFiltersChanged));
    form.addEventListener('change', event => {
        if (event.target === form.elements.year) {
            start.value = '';
            end.value = '';
        }
        markFiltersChanged();
    });
    validatePeriod();
    updateSummary();
})();
