import { apiFetch, fetchAllPages } from "/static/js/api.js";
import {
  STATUSES,
  escapeHtml,
  formToObject,
  queueToast,
  setButtonLoading,
  showModal,
  showToast,
  todayISO,
} from "/static/js/utils.js";

function showFormError(form, message) {
  const box = form.querySelector(".form-error");
  box.textContent = message;
  box.classList.toggle("d-none", !message);
}

function fillForm(form, values) {
  for (const element of form.elements) {
    if (!element.name || !(element.name in values)) {
      continue;
    }
    const value = values[element.name] ?? "";
    if (element.tagName === "SELECT" && value && ![...element.options].some((option) => option.value === value)) {
      element.add(new Option(value, value));
    }
    element.value = value;
  }
}

const companyForm = document.getElementById("companyForm");
let editingCompany = null;

export function openCompanyForm(company = null) {
  editingCompany = company;
  companyForm.reset();
  showFormError(companyForm, "");
  document.getElementById("companyModalLabel").textContent = company ? "Edit company" : "New company";
  companyForm.querySelector("[type=submit]").textContent = company ? "Save changes" : "Create company";
  if (company) {
    fillForm(companyForm, company);
  }
  showModal("companyModal");
}

companyForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = companyForm.querySelector("[type=submit]");
  const data = formToObject(companyForm);
  showFormError(companyForm, "");
  setButtonLoading(submitButton, true);

  try {
    if (editingCompany) {
      await apiFetch(`/api/companies/${encodeURIComponent(editingCompany.company_id)}`, { method: "PATCH", body: data });
      queueToast("Company updated");
      window.location.reload();
    } else {
      const company = await apiFetch("/api/companies", { method: "POST", body: data });
      queueToast(`${company.company_name} added`);
      window.location.href = `/companies/${encodeURIComponent(company.company_id)}`;
    }
  } catch (error) {
    showFormError(companyForm, error.message);
    setButtonLoading(submitButton, false);
  }
});

const jobForm = document.getElementById("jobForm");
let editingJob = null;

async function loadCompanyOptions(selectedId) {
  const select = jobForm.company_id;
  select.innerHTML = '<option value="">Loading companies...</option>';
  try {
    const companies = await fetchAllPages("/api/companies", "companies");
    if (companies.length === 0) {
      select.innerHTML = '<option value="">No companies yet. Add a company first.</option>';
      return;
    }
    select.innerHTML =
      '<option value="">Choose a company</option>' +
      companies
        .map((company) => `<option value="${escapeHtml(company.company_id)}">${escapeHtml(company.company_name)}</option>`)
        .join("");
    select.value = selectedId ?? "";
  } catch (error) {
    select.innerHTML = '<option value="">Could not load companies</option>';
    showToast(error.message, "danger");
  }
}

export function openJobForm(job = null, { companyId = null } = {}) {
  editingJob = job;
  jobForm.reset();
  showFormError(jobForm, "");
  document.getElementById("jobModalLabel").textContent = job ? "Edit job" : "New job";
  jobForm.querySelector("[type=submit]").textContent = job ? "Save changes" : "Create job";
  if (job) {
    fillForm(jobForm, job);
  } else {
    jobForm.job_posting_date.value = todayISO();
  }
  loadCompanyOptions(job?.company_id ?? companyId);
  showModal("jobModal");
}

jobForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = jobForm.querySelector("[type=submit]");
  const data = formToObject(jobForm);
  data.salary_currency = data.salary_currency?.toUpperCase() ?? null;
  showFormError(jobForm, "");
  setButtonLoading(submitButton, true);

  try {
    if (editingJob) {
      await apiFetch(`/api/jobs/${encodeURIComponent(editingJob.job_id)}`, { method: "PATCH", body: data });
      queueToast("Job updated");
      window.location.reload();
    } else {
      const job = await apiFetch("/api/jobs", { method: "POST", body: data });
      queueToast(`${job.role} added`);
      window.location.href = `/jobs/${encodeURIComponent(job.job_id)}`;
    }
  } catch (error) {
    showFormError(jobForm, error.message);
    setButtonLoading(submitButton, false);
  }
});

const quickForm = document.getElementById("quickApplicationForm");
quickForm.current_status.innerHTML = STATUSES.map((status) => `<option>${status}</option>`).join("");

export async function openQuickApplicationForm({ companyName = null } = {}) {
  quickForm.reset();
  quickForm.querySelectorAll("details").forEach((section) => (section.open = false));
  quickForm.company_name.value = companyName ?? "";
  showFormError(quickForm, "");
  quickForm.current_status.value = "Applied";
  quickForm.date_applied.value = todayISO();
  showModal("quickApplicationModal");

  try {
    const companies = await fetchAllPages("/api/companies", "companies");
    document.getElementById("quickCompanyOptions").innerHTML = companies
      .map((company) => `<option value="${escapeHtml(company.company_name)}"></option>`)
      .join("");
  } catch {
  }
}

quickForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = quickForm.querySelector("[type=submit]");
  showFormError(quickForm, "");
  setButtonLoading(submitButton, true);
  try {
    const data = formToObject(quickForm);
    data.salary_currency = data.salary_currency?.toUpperCase() ?? null;
    await apiFetch("/api/applications/quick", { method: "POST", body: data });
    queueToast("Application added");
    if (window.location.pathname === "/") {
      window.location.reload();
    } else {
      window.location.href = "/";
    }
  } catch (error) {
    showFormError(quickForm, error.message);
    setButtonLoading(submitButton, false);
  }
});
