// JS per categorie:
// - gestione click "Modifica" in categories/list
// - gestione checkbox "seleziona tutti" in assign_bulk

document.addEventListener("DOMContentLoaded", () => {
  setupCategoryEditButtons();
  setupBulkAssignCheckboxes();
});

function setupCategoryEditButtons() {
  const table = document.getElementById("categories-table");
  const form = document.querySelector("form[action$='/categories/save']");
  if (!table || !form) return;

  const idInput = form.querySelector("#category_id");
  const nameInput = form.querySelector("#name");
  const descInput = form.querySelector("#description");
  const resetBtn = document.getElementById("category-form-reset");

  table.addEventListener("click", (event) => {
    const btn = event.target.closest(".category-edit-btn");
    if (!btn) return;

    const row = btn.closest("tr");
    if (!row) return;

    const id = row.getAttribute("data-category-id");
    const name = row.getAttribute("data-category-name") || "";
    const description = row.getAttribute("data-category-description") || "";

    idInput.value = id || "";
    nameInput.value = name;
    descInput.value = description;
  });

  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      idInput.value = "";
    });
  }
}

function setupBulkAssignCheckboxes() {
  const selectAll = document.getElementById("select_all_rows");
  const checkboxes = document.querySelectorAll(".line-checkbox");
  if (!selectAll || !checkboxes.length) return;

  selectAll.addEventListener("change", () => {
    const checked = selectAll.checked;
    checkboxes.forEach((cb) => {
      cb.checked = checked;
    });
  });
}
