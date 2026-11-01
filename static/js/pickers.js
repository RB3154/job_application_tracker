import { apiFetch } from "/static/js/api.js";
import { escapeHtml, showToast } from "/static/js/utils.js";

let pickerCount = 0;

export function createPicker(element, { endpoint, noun, extra = null }) {
  const listId = `picker-options-${++pickerCount}`;
  element.innerHTML = `
    <ul class="list-unstyled picker-items mb-2"></ul>
    <div class="input-group input-group-sm">
      <input type="text" class="form-control" list="${listId}" placeholder="Type a ${escapeHtml(noun)} and press Enter" aria-label="Add a ${escapeHtml(noun)}">
      <button type="button" class="btn btn-outline-primary">Add</button>
    </div>
    <datalist id="${listId}"></datalist>`;

  const itemsList = element.querySelector(".picker-items");
  const input = element.querySelector("input");
  const addButton = element.querySelector("button");
  const datalist = element.querySelector("datalist");

  let options = [];
  let selected = [];

  function renderOptions() {
    datalist.innerHTML = options.map((option) => `<option value="${escapeHtml(option.name)}"></option>`).join("");
  }

  function extraControl(item) {
    if (extra === "skillType") {
      return `
        <select class="form-select form-select-sm picker-extra" aria-label="How important is ${escapeHtml(item.name)}">
          <option value="required" ${item.skill_type !== "preferred" ? "selected" : ""}>Required</option>
          <option value="preferred" ${item.skill_type === "preferred" ? "selected" : ""}>Nice to have</option>
        </select>`;
    }
    if (extra === "note") {
      return `<input type="text" class="form-control form-control-sm picker-extra" placeholder="Note (optional)"
                aria-label="Note for ${escapeHtml(item.name)}" value="${escapeHtml(item.note ?? "")}">`;
    }
    return "";
  }

  function renderSelected() {
    if (selected.length === 0) {
      itemsList.innerHTML = `<li class="text-muted-soft small">None yet.</li>`;
      return;
    }
    itemsList.innerHTML = selected
      .map(
        (item, index) => `
        <li class="picker-item" data-index="${index}">
          <span class="picker-name">${escapeHtml(item.name)}</span>
          ${extraControl(item)}
          <button type="button" class="btn-close" aria-label="Remove ${escapeHtml(item.name)}"></button>
        </li>`,
      )
      .join("");
  }

  function readExtras() {
    itemsList.querySelectorAll(".picker-item").forEach((row) => {
      const control = row.querySelector(".picker-extra");
      if (!control) {
        return;
      }
      const item = selected[Number(row.dataset.index)];
      if (extra === "skillType") {
        item.skill_type = control.value;
      } else if (extra === "note") {
        item.note = control.value.trim() || null;
      }
    });
  }

  async function addTyped() {
    const name = input.value.trim();
    if (!name) {
      return;
    }
    let option = options.find((candidate) => candidate.name.toLowerCase() === name.toLowerCase());
    if (!option) {
      try {
        option = await apiFetch(endpoint, { method: "POST", body: { name } });
      } catch (error) {
        showToast(error.message, "danger");
        return;
      }
      options.push(option);
      options.sort((a, b) => a.name.localeCompare(b.name));
      renderOptions();
    }
    readExtras();
    if (!selected.some((item) => item.id === option.id)) {
      selected.push({ ...option, skill_type: "required", note: null });
      renderSelected();
    }
    input.value = "";
    input.focus();
  }

  addButton.addEventListener("click", addTyped);
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addTyped();
    }
  });
  itemsList.addEventListener("click", (event) => {
    const removeButton = event.target.closest(".btn-close");
    if (removeButton) {
      readExtras();
      selected.splice(Number(removeButton.closest(".picker-item").dataset.index), 1);
      renderSelected();
    }
  });

  return {
    async load() {
      options = await apiFetch(endpoint);
      renderOptions();
    },
    setSelected(items) {
      selected = items.map((item) => ({ ...item }));
      input.value = "";
      renderSelected();
    },
    getSelected() {
      readExtras();
      return selected.map((item) => ({ ...item }));
    },
  };
}
