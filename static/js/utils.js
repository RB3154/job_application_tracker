// Small helpers shared by the pages: safe HTML, formatting, toasts and dialogs.
// The format* functions match the Jinja macros in templates/_macros.html, so cards
// added by "Load more" look the same as the ones rendered by the server.

// Same list as ApplicationStatus in schemas.py.
export const STATUSES = ["Wishlist", "Applied", "Screening", "Interview", "Offer", "Accepted", "Rejected", "Withdrawn"];

// XSS prevention: always escape text from the API before putting it into innerHTML.
export function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

// Only allow http(s) links, so a saved "javascript:..." URL can't run code when clicked.
export function safeUrl(url) {
  return /^https?:\/\//i.test(url ?? "") ? url : null;
}

// Parse "2026-10-29" as a local date. new Date("2026-10-29") would read it as UTC
// midnight, which shows as the previous day in timezones behind UTC.
function parseDate(dateString) {
  const [year, month, day] = dateString.split("-").map(Number);
  return new Date(year, month - 1, day);
}

// "2026-10-29" -> "Oct 29, 2026"
export function formatDate(dateString) {
  if (!dateString) {
    return "";
  }
  return parseDate(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// Today as "YYYY-MM-DD" in the user's timezone (the format <input type="date"> uses).
export function todayISO() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  return new Date(now - offset).toISOString().slice(0, 10);
}

function formatNumber(value) {
  return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function formatSalary(job) {
  const { salary_min: min, salary_max: max, salary_currency: currency, salary_period: period } = job;
  if (min == null && max == null) {
    return job.salary_text || "";
  }
  let range;
  if (min != null && max != null) {
    range = `${formatNumber(min)} – ${formatNumber(max)}`;
  } else if (min != null) {
    range = `${formatNumber(min)}+`;
  } else {
    range = `up to ${formatNumber(max)}`;
  }
  return `${currency ? currency + " " : ""}${range}${period ? " / " + period : ""}`;
}

export function formatExperience(job) {
  const { exp_min: min, exp_max: max } = job;
  if (min != null && max != null) {
    return `${Number(min)}–${Number(max)} yrs`;
  }
  if (min != null) {
    return `${Number(min)}+ yrs`;
  }
  if (max != null) {
    return `up to ${Number(max)} yrs`;
  }
  return job.exp_text || "";
}

export function statusBadge(status) {
  const value = status || "Applied";
  return `<span class="status-badge status-${value.toLowerCase()}">${escapeHtml(value)}</span>`;
}

export function deadlineBadge(deadline) {
  if (!deadline) {
    return "";
  }
  const days = Math.round((parseDate(deadline) - parseDate(todayISO())) / 86400000);
  if (days < 0) {
    return '<span class="badge text-bg-secondary">Closed</span>';
  }
  if (days === 0) {
    return '<span class="badge text-bg-danger">Closes today</span>';
  }
  if (days <= 7) {
    return `<span class="badge text-bg-warning">Closes in ${days} day${days === 1 ? "" : "s"}</span>`;
  }
  return `<span class="badge bg-body-secondary text-body">Apply by ${formatDate(deadline)}</span>`;
}

// First letter for avatars and company "logos".
export function initial(text) {
  return escapeHtml((text || "?").trim().charAt(0).toUpperCase());
}

// The user's uploaded picture, or a colored circle with their first letter.
export function avatarHtml(user, size = 32) {
  if (user.image_path) {
    return `<img class="avatar" src="${escapeHtml(user.image_path)}" alt="" width="${size}" height="${size}">`;
  }
  return `<span class="avatar avatar-initial" style="width:${size}px;height:${size}px;font-size:${size * 0.45}px">${initial(user.username)}</span>`;
}

// Read a form into a plain object. Empty fields become null, so optional values are cleared.
export function formToObject(form) {
  const data = {};
  for (const [key, value] of new FormData(form).entries()) {
    const trimmed = typeof value === "string" ? value.trim() : value;
    data[key] = trimmed === "" ? null : trimmed;
  }
  return data;
}

// Disable a button and show a spinner while a request runs.
export function setButtonLoading(button, loading, loadingText = "Saving...") {
  if (loading) {
    button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>${escapeHtml(loadingText)}`;
  } else {
    button.disabled = false;
    button.innerHTML = button.dataset.originalHtml ?? button.innerHTML;
  }
}

// A small message in the bottom-right corner that disappears by itself.
export function showToast(message, type = "success") {
  const icons = { success: "bi-check-circle-fill", danger: "bi-exclamation-triangle-fill", info: "bi-info-circle-fill" };
  const toast = document.createElement("div");
  toast.className = `toast align-items-center text-bg-${type} border-0`;
  toast.setAttribute("role", type === "danger" ? "alert" : "status");
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body"><i class="bi ${icons[type] ?? icons.info} me-2"></i>${escapeHtml(message)}</div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
    </div>`;
  document.getElementById("toastContainer").append(toast);
  toast.addEventListener("hidden.bs.toast", () => toast.remove());
  bootstrap.Toast.getOrCreateInstance(toast, { delay: type === "danger" ? 6000 : 3500 }).show();
}

// A toast to show on the *next* page, for when we redirect or reload right after saving.
export function queueToast(message, type = "success") {
  try {
    sessionStorage.setItem("queuedToast", JSON.stringify({ message, type }));
  } catch {
    // Storage blocked (e.g. private mode): the redirect still happens, just without the message.
  }
}

export function showQueuedToast() {
  try {
    const queued = JSON.parse(sessionStorage.getItem("queuedToast"));
    sessionStorage.removeItem("queuedToast");
    if (queued) {
      showToast(queued.message, queued.type);
    }
  } catch {
    // Nothing queued, or storage blocked.
  }
}

export function showModal(modalId) {
  const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById(modalId));
  modal.show();
  return modal;
}

export function hideModal(modalId) {
  bootstrap.Modal.getInstance(document.getElementById(modalId))?.hide();
}

// "Are you sure?" dialog. Resolves to true if the user clicks the confirm button.
export function confirmDialog(message, { title = "Are you sure?", confirmText = "Delete" } = {}) {
  const modalElement = document.getElementById("confirmModal");
  modalElement.querySelector(".modal-title").textContent = title;
  modalElement.querySelector(".confirm-message").textContent = message;
  const confirmButton = modalElement.querySelector(".confirm-btn");
  confirmButton.textContent = confirmText;

  return new Promise((resolve) => {
    let confirmed = false;
    const onConfirm = () => {
      confirmed = true;
      hideModal("confirmModal");
    };
    confirmButton.addEventListener("click", onConfirm, { once: true });
    modalElement.addEventListener(
      "hidden.bs.modal",
      () => {
        confirmButton.removeEventListener("click", onConfirm);
        resolve(confirmed);
      },
      { once: true },
    );
    showModal("confirmModal");
  });
}
