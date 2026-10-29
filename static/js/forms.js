// The "New / Edit company" and "New / Edit job" modals from layout.html.
// They are opened from the navbar ("Add" menu) and from the company and job pages.

import { apiFetch, fetchAllPages } from "/static/js/api.js";
import { escapeHtml, formToObject, queueToast, setButtonLoading, showModal, showToast, slugify, todayISO } from "/static/js/utils.js";

function showFormError(form, message) {
  const box = form.querySelector(".form-error");
  box.textContent = message;
  box.classList.toggle("d-none", !message);
}

// Keep suggesting an id (e.g. "google" from "Google") until the user types their own.
function suggestIdFrom(sourceInputs, idInput, makeId) {
  idInput.addEventListener("input", () => {
    idInput.dataset.touched = "true";
  });
  for (const input of sourceInputs) {
    input.addEventListener("input", () => {
      if (!idInput.dataset.touched && !idInput.readOnly) {
        idInput.value = makeId();
      }
    });
  }
}

function fillForm(form, values) {
  for (const element of form.elements) {
    if (!element.name || !(element.name in values)) {
      continue;
    }
    const value = values[element.name] ?? "";
    // Keep a saved value that isn't one of the dropdown's options (e.g. salary period "annum").
    if (element.tagName === "SELECT" && value && ![...element.options].some((option) => option.value === value)) {
      element.add(new Option(value, value));
    }
    element.value = value;
  }
}

/* ---------- Company form ---------- */

const companyForm = document.getElementById("companyForm");
let editingCompany = null;

suggestIdFrom([companyForm.company_name], companyForm.company_id, () => slugify(companyForm.company_name.value));

export function openCompanyForm(company = null) {
  editingCompany = company;
  companyForm.reset();
  showFormError(companyForm, "");
  document.getElementById("companyModalLabel").textContent = company ? "Edit company" : "New company";
  companyForm.querySelector("[type=submit]").textContent = company ? "Save changes" : "Create company";
  companyForm.company_id.readOnly = Boolean(company);
  companyForm.company_id.dataset.touched = company ? "true" : "";
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
      delete data.company_id;
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

/* ---------- Job form ---------- */

const jobForm = document.getElementById("jobForm");
let editingJob = null;

suggestIdFrom([jobForm.role, jobForm.company_id], jobForm.job_id, () =>
  slugify(`${jobForm.company_id.value} ${jobForm.role.value}`),
);

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

// `companyId` preselects a company, e.g. when adding a job from a company's page.
export function openJobForm(job = null, { companyId = null } = {}) {
  editingJob = job;
  jobForm.reset();
  showFormError(jobForm, "");
  document.getElementById("jobModalLabel").textContent = job ? "Edit job" : "New job";
  jobForm.querySelector("[type=submit]").textContent = job ? "Save changes" : "Create job";
  jobForm.job_id.readOnly = Boolean(job);
  jobForm.job_id.dataset.touched = job ? "true" : "";
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
      delete data.job_id;
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
