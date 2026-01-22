(() => {
  const filterForm = document.getElementById("documents-filters-form");
  if (filterForm) {
    filterForm.addEventListener("submit", () => {
      const formData = new FormData(filterForm);
      const params = new URLSearchParams();

      for (const [key, value] of formData.entries()) {
        const trimmed = String(value || "").trim();
        if (trimmed) {
          params.set(key, trimmed);
        }
      }

      const query = params.toString();
      if (query) {
        localStorage.setItem("documents:lastFilters", `?${query}`);
      } else {
        localStorage.removeItem("documents:lastFilters");
      }
    });
  }

  const resumeButton = document.getElementById("resume-last-filters");
  if (resumeButton) {
    const saved = localStorage.getItem("documents:lastFilters");
    if (saved && saved !== "?") {
      resumeButton.classList.remove("d-none");
      resumeButton.addEventListener("click", () => {
        const target = saved.startsWith("?") ? saved : `?${saved}`;
        window.location.search = target;
      });
    }
  }

  const rows = document.querySelectorAll(".documents-row[data-href]");
  rows.forEach((row) => {
    row.addEventListener("click", (event) => {
      if (event.target.closest("a, button, input, select, textarea, label")) {
        return;
      }
      const href = row.getAttribute("data-href");
      if (href) {
        window.location.href = href;
      }
    });
  });
})();
