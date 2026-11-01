const TOKEN_KEY = "access_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
  userPromise = null;
}

export async function endSession() {
  try {
    await fetch("/api/users/logout", { method: "POST" });
  } catch {
  }
  clearToken();
}

export async function logout() {
  await endSession();
  window.location.href = "/";
}

export function redirectToLogin() {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = `/login?next=${next}`;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

export function getErrorMessage(data) {
  if (typeof data?.detail === "string") {
    return data.detail;
  }
  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((error) => {
        const field = error.loc?.at(-1);
        const message = error.msg.replace(/^Value error, /, "");
        return typeof field === "string" && field !== "body" ? `${field}: ${message}` : message;
      })
      .join(". ");
  }
  return "Something went wrong. Please try again.";
}

export async function apiFetch(path, { method = "GET", body, redirectOn401 = true } = {}) {
  const headers = {};
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let requestBody = body;
  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(path, { method, headers, body: requestBody });
  } catch {
    throw new ApiError("Network error. Check your connection and try again.", 0);
  }

  if (response.status === 401 && token) {
    clearToken();
    if (redirectOn401) {
      redirectToLogin();
    }
    throw new ApiError("Your session has expired. Please log in again.", 401);
  }

  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(getErrorMessage(data), response.status);
  }
  return data;
}

let userPromise = null;

export function getCurrentUser() {
  if (!getToken()) {
    return Promise.resolve(null);
  }
  userPromise ??= apiFetch("/api/users/me", { redirectOn401: false }).catch(() => null);
  return userPromise;
}

export async function requireUser() {
  const user = await getCurrentUser();
  if (!user) {
    redirectToLogin();
  }
  return user;
}

export async function fetchAllPages(path, key) {
  const items = [];
  let skip = 0;
  while (true) {
    const page = await apiFetch(`${path}?skip=${skip}&limit=100`);
    items.push(...page[key]);
    if (!page.has_more || page[key].length === 0) {
      return items;
    }
    skip += page[key].length;
  }
}

const jobCache = new Map();
const companyCache = new Map();

function cachedGet(cache, url) {
  if (!cache.has(url)) {
    cache.set(url, apiFetch(url).catch(() => null));
  }
  return cache.get(url);
}

export function getJob(jobId) {
  return cachedGet(jobCache, `/api/jobs/${encodeURIComponent(jobId)}`);
}

export function getCompany(companyId) {
  return cachedGet(companyCache, `/api/companies/${encodeURIComponent(companyId)}`);
}
