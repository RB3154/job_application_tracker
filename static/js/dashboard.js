import { apiFetch, fetchAllPages, getCompany, getCurrentUser, getJob } from "/static/js/api.js";
import { STATUSES, confirmDialog, deadlineBadge, escapeHtml, formatDate, showToast } from "/static/js/utils.js";

const ACTIVE_STATUSES = ["Applied", "Screening", "Interview"];
const CLOSED_STATUSES = ["Accepted", "Rejected", "Withdrawn"];

const BOARD_COLUMNS = [
  { title: "Wishlist", statuses: ["Wishlist"] },
  { title: "Applied", statuses: ["Applied"] },
  { title: "Screening", statuses: ["Screening"] },
  { title: "Interview", statuses: ["Interview"] },
  { title: "Offer", statuses: ["Offer"] },
  { title: "Closed", statuses: CLOSED_STATUSES, foldable: true },
];

const DEADLINE_WARNING_DAYS = 7;
const FOLLOW_UP_AFTER_DAYS = 14;

const VIEW_STORAGE_KEY = "dashboardView";

let applications = [];
let statusFilter = "All";
let searchText = "";
let view = loadSavedView();
let closedColumnOpen = false;

const statsElement = document.getElementById("stats");
const filtersElement = document.getElementById("statusFilters");
const tbody = document.getElementById("applicationsBody");
const emptyState = document.getElementById("emptyState");
const tableView = document.getElementById("tableView");
const boardView = document.getElementById("boardView");
const viewToggle = document.getElementById("viewToggle");
const attentionPanel = document.getElementById("attentionPanel");

function show(stateId) {
  for (const id of ["loadingState", "welcomeState", "dashboardState"]) {
    document.getElementById(id).classList.toggle("d-none", id !== stateId);
  }
}

function loadSavedView() {
  try {
    return localStorage.getItem(VIEW_STORAGE_KEY) === "board" ? "board" : "table";
  } catch {
    return "table";
  }
}

function saveView() {
  try {
    localStorage.setItem(VIEW_STORAGE_KEY, view);
  } catch {
  }
}

function daysSince(value) {
  const day = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
  day.setHours(0, 0, 0, 0);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((today - day) / 86400000);
}

function countBy(statuses) {
  return applications.filter((app) => statuses.includes(app.current_status)).length;
}

function roleOf(app) {
  return app.job?.role ?? `Deleted job (${app.job_id})`;
}

function companyOf(app) {
  return app.company?.company_name ?? app.job?.company_id ?? "";
}

function statusSelectHTML(app) {
  const options = STATUSES.map(
    (status) => `<option ${status === app.current_status ? "selected" : ""}>${status}</option>`,
  ).join("");
  const statusClass = `status-${(app.current_status ?? "Applied").toLowerCase()}`;
  return `
    <select class="form-select form-select-sm status-select ${statusClass}" data-action="status" aria-label="Status for ${escapeHtml(roleOf(app))}">
      ${options}
    </select>`;
}

function visibleApplications() {
  const query = searchText.toLowerCase();
  return applications.filter((app) => {
    const matchesStatus = statusFilter === "All" || app.current_status === statusFilter;
    const haystack = `${app.job?.role ?? ""} ${app.company?.company_name ?? ""}`.toLowerCase();
    return matchesStatus && haystack.includes(query);
  });
}

function renderStats() {
  const total = applications.length - countBy(["Wishlist"]);
  const considered = total - countBy(["Withdrawn"]);
  const heardBack = considered - countBy(["Applied"]);
  const responseRate = considered > 0 ? `${Math.round((heardBack / considered) * 100)}%` : "–";

  const stats = [
    { label: "Total applications", value: total, icon: "bi-send" },
    { label: "Wishlist", value: countBy(["Wishlist"]), icon: "bi-bookmark" },
    { label: "Active", value: countBy(ACTIVE_STATUSES), icon: "bi-hourglass-split" },
    { label: "Interviewing", value: countBy(["Interview"]), icon: "bi-people" },
    { label: "Offers", value: countBy(["Offer", "Accepted"]), icon: "bi-trophy" },
    { label: "Response rate", value: responseRate, icon: "bi-reply" },
  ];
  statsElement.innerHTML = stats
    .map(
      (stat) => `
      <div class="col-6 col-md-4 col-xl">
        <div class="content-section stat-card">
          <div class="d-flex justify-content-between align-items-start">
            <div class="stat-value">${stat.value}</div>
            <i class="bi ${stat.icon} text-muted-soft fs-5"></i>
          </div>
          <div class="stat-label mt-1">${stat.label}</div>
        </div>
      </div>`,
    )
    .join("");
}

function renderFilters() {
  const options = ["All", ...STATUSES];
  filtersElement.innerHTML = options
    .map((status) => {
      const count = status === "All" ? applications.length : countBy([status]);
      const active = status === statusFilter;
      return `<button type="button" class="filter-pill ${active ? "active" : ""}" data-status="${status}" aria-pressed="${active}">
                ${status}<span class="count">${count}</span>
              </button>`;
    })
    .join("");
}

function attentionItems() {
  const items = [];
  for (const app of applications) {
    const deadline = app.job?.application_deadline;
    if (app.current_status === "Wishlist" && deadline) {
      const daysLeft = -daysSince(deadline);
      if (daysLeft <= DEADLINE_WARNING_DAYS) {
        const when =
          daysLeft < 0 ? "the deadline has passed" : daysLeft === 0 ? "closes today" : `closes in ${daysLeft} day${daysLeft === 1 ? "" : "s"}`;
        items.push({ app, icon: "bi-alarm", text: `On your wishlist and ${when}`, sortKey: daysLeft });
      }
    }
    if (app.current_status === "Applied") {
      const quietDays = daysSince(app.last_status_change ?? app.date_applied);
      if (quietDays >= FOLLOW_UP_AFTER_DAYS) {
        items.push({ app, icon: "bi-hourglass-bottom", text: `Applied ${quietDays} days ago with no update. Time to follow up?`, sortKey: 1000 - quietDays });
      }
    }
  }
  return items.sort((a, b) => a.sortKey - b.sortKey);
}

function renderAttention() {
  const items = attentionItems();
  attentionPanel.classList.toggle("d-none", items.length === 0);
  if (items.length === 0) {
    attentionPanel.innerHTML = "";
    return;
  }
  attentionPanel.innerHTML = `
    <h2 class="section-title mb-2" id="attentionTitle"><i class="bi bi-bell me-1"></i>Needs attention</h2>
    <ul class="list-unstyled mb-0">
      ${items
        .map(
          ({ app, icon, text }) => `
          <li class="attention-item">
            <i class="bi ${icon} text-muted-soft"></i>
            <span>
              <a class="fw-semibold" href="/jobs/${encodeURIComponent(app.job_id)}">${escapeHtml(roleOf(app))}</a>
              <span class="text-muted-soft">at ${escapeHtml(companyOf(app))}</span>: ${escapeHtml(text)}
            </span>
          </li>`,
        )
        .join("")}
    </ul>`;
}

function rowHTML(app) {
  return `
    <tr data-id="${app.application_id}">
      <td class="ps-3">
        <a class="fw-semibold" href="/jobs/${encodeURIComponent(app.job_id)}">${escapeHtml(roleOf(app))}</a>
        <div class="small text-muted-soft">${escapeHtml(companyOf(app))}</div>
      </td>
      <td class="text-nowrap">
        ${formatDate(app.date_applied)}
        <div class="small text-muted-soft">${app.current_status === "Wishlist" ? "saved" : "applied"}</div>
      </td>
      <td>${statusSelectHTML(app)}</td>
      <td class="text-end pe-3">
        <button type="button" class="btn btn-sm btn-link text-danger" data-action="delete" aria-label="Delete application" title="Delete application">
          <i class="bi bi-trash"></i>
        </button>
      </td>
    </tr>`;
}

function renderTable(visible) {
  tbody.innerHTML = visible.map(rowHTML).join("");
}

function cardHTML(app) {
  const isClosed = CLOSED_STATUSES.includes(app.current_status);
  const rounds = app.interview_rounds
    ? `<span title="Interview rounds"><i class="bi bi-people"></i> ${app.interview_rounds}</span>`
    : "";
  const notes = app.notes ? `<span title="Has notes"><i class="bi bi-sticky"></i></span>` : "";
  return `
    <article class="board-card" data-id="${app.application_id}">
      <a class="fw-semibold d-block" href="/jobs/${encodeURIComponent(app.job_id)}">${escapeHtml(roleOf(app))}</a>
      <div class="small text-muted-soft mb-2">${escapeHtml(companyOf(app))}</div>
      ${!isClosed && app.current_status === "Wishlist" ? `<div class="mb-2">${deadlineBadge(app.job?.application_deadline)}</div>` : ""}
      <div class="board-card-meta small text-muted-soft mb-2">
        <span>${app.current_status === "Wishlist" ? "Saved" : "Applied"} ${formatDate(app.date_applied)}</span>
        ${rounds}
        ${notes}
      </div>
      ${statusSelectHTML(app)}
    </article>`;
}

function renderBoard(visible) {
  boardView.innerHTML = BOARD_COLUMNS.map((column) => {
    const cards = visible.filter((app) => column.statuses.includes(app.current_status));
    const folded = column.foldable && !closedColumnOpen;
    const header = column.foldable
      ? `<button type="button" class="btn btn-link btn-sm p-0 text-reset text-decoration-none" data-action="toggle-closed" aria-expanded="${!folded}">
           <i class="bi ${folded ? "bi-chevron-right" : "bi-chevron-down"}"></i> ${column.title}
         </button>`
      : column.title;
    const body = folded
      ? ""
      : cards.length
        ? cards.map(cardHTML).join("")
        : `<p class="small text-muted-soft mb-0">Nothing here.</p>`;
    return `
      <section class="board-column ${folded ? "folded" : ""}" aria-label="${column.title}">
        <h2 class="board-column-title">${header}<span class="count">${cards.length}</span></h2>
        ${body}
      </section>`;
  }).join("");
}

function renderView() {
  const visible = visibleApplications();
  for (const button of viewToggle.querySelectorAll("[data-view]")) {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active);
  }

  if (view === "board") {
    renderBoard(visible);
  } else {
    renderTable(visible);
  }

  if (applications.length === 0) {
    emptyState.innerHTML = `
      <i class="bi bi-inbox"></i>
      <p class="mb-3">You haven't tracked any applications yet.</p>
      <button type="button" class="btn btn-primary" data-open-form="application"><i class="bi bi-plus-lg me-1"></i>Add your first application</button>
      <p class="small mt-3 mb-0">Just the company, role and link; you can fill in the rest later.</p>`;
  } else {
    emptyState.innerHTML = `<i class="bi bi-funnel"></i><p class="mb-0">No applications match this filter.</p>`;
  }
  const nothingToShow = visible.length === 0;
  emptyState.classList.toggle("d-none", !nothingToShow);
  tableView.classList.toggle("d-none", view !== "table" || nothingToShow);
  boardView.classList.toggle("d-none", view !== "board" || nothingToShow);
}

function renderAll() {
  renderStats();
  renderFilters();
  renderAttention();
  renderView();
}

async function updateApplication(app, changes) {
  try {
    const updated = await apiFetch(`/api/applications/${app.application_id}`, { method: "PATCH", body: changes });
    const lastStatusChange = changes.current_status ? new Date().toISOString() : app.last_status_change;
    Object.assign(app, updated, { last_status_change: lastStatusChange });
    showToast("Application updated");
  } catch (error) {
    showToast(error.message, "danger");
  }
  renderAll();
}

function applicationFor(element) {
  const id = Number(element.closest("[data-id]").dataset.id);
  return applications.find((item) => item.application_id === id);
}

filtersElement.addEventListener("click", (event) => {
  const button = event.target.closest("[data-status]");
  if (button) {
    statusFilter = button.dataset.status;
    renderFilters();
    renderView();
  }
});

document.getElementById("searchInput").addEventListener("input", (event) => {
  searchText = event.target.value.trim();
  renderView();
});

viewToggle.addEventListener("click", (event) => {
  const button = event.target.closest("[data-view]");
  if (button && button.dataset.view !== view) {
    view = button.dataset.view;
    saveView();
    renderView();
  }
});

for (const container of [tbody, boardView]) {
  container.addEventListener("change", (event) => {
    if (event.target.dataset.action === "status") {
      updateApplication(applicationFor(event.target), { current_status: event.target.value });
    }
  });
}

boardView.addEventListener("click", (event) => {
  if (event.target.closest("[data-action='toggle-closed']")) {
    closedColumnOpen = !closedColumnOpen;
    renderView();
  }
});

tbody.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }
  const app = applicationFor(button);

  if (button.dataset.action === "delete") {
    const confirmed = await confirmDialog(`Stop tracking your application for "${roleOf(app)}"?`, { title: "Delete application?" });
    if (!confirmed) {
      return;
    }
    try {
      await apiFetch(`/api/applications/${app.application_id}`, { method: "DELETE" });
      applications = applications.filter((item) => item !== app);
      showToast("Application deleted");
      renderAll();
    } catch (error) {
      showToast(error.message, "danger");
    }
  }
});

async function loadDashboard(user) {
  document.getElementById("greeting").textContent = `Hi, ${user.username}`;
  const items = await fetchAllPages("/api/applications", "applications");
  applications = await Promise.all(
    items.map(async (app) => {
      const job = await getJob(app.job_id);
      const company = job ? await getCompany(job.company_id) : null;
      return { ...app, job, company };
    }),
  );
  renderAll();
  show("dashboardState");
}

const user = await getCurrentUser();
if (!user) {
  show("welcomeState");
} else {
  try {
    await loadDashboard(user);
  } catch (error) {
    show("dashboardState");
    emptyState.innerHTML = `<i class="bi bi-exclamation-triangle"></i><p class="mb-0">${escapeHtml(error.message)}</p>`;
    emptyState.classList.remove("d-none");
  }
}
