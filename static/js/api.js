// Everything that talks to our FastAPI backend: the login token, the logged-in
// user, and apiFetch(), a small wrapper around fetch() that every page uses.

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

// End the session everywhere: the login cookie that pages use (server) and the token (this browser).
export async function endSession() {
  try {
    await fetch("/api/users/logout", { method: "POST" });
  } catch {
    // Offline: the cookie expires on its own together with the token.
  }
  clearToken();
}

export async function logout() {
  await endSession();
  window.location.href = "/";
}

// Send the user to the login page, remembering where to come back to afterwards.
export function redirectToLogin() {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = `/login?next=${next}`;
}

// Error thrown by apiFetch(); `status` is the HTTP status code (0 for network errors).
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// Turn FastAPI's error body into one readable sentence.
// HTTPException gives {"detail": "text"}; validation errors give {"detail": [{msg: ...}, ...]}.
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

/**
 * Call one of our /api endpoints and return the parsed JSON (or null for 204 No Content).
 *
 * - Adds the "Authorization: Bearer <token>" header when the user is logged in.
 * - Sends plain objects as JSON, and FormData (file uploads, the login form) as-is.
 * - On 401 the token is expired or invalid: it's removed and, unless
 *   redirectOn401 is false, the user is sent to the login page.
 * - Throws ApiError with a readable message when the response is not OK.
 */
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

  // A 401 with a token means the token expired. (Without one it's e.g. a wrong password on login.)
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

// The logged-in user from GET /api/users/me, or null when logged out.
// The request runs once per page load; every caller shares the same promise.
let userPromise = null;

export function getCurrentUser() {
  if (!getToken()) {
    return Promise.resolve(null);
  }
  userPromise ??= apiFetch("/api/users/me", { redirectOn401: false }).catch(() => null);
  return userPromise;
}

// Same as getCurrentUser(), but sends logged-out visitors to the login page.
export async function requireUser() {
  const user = await getCurrentUser();
  if (!user) {
    redirectToLogin();
  }
  return user;
}

/**
 * Fetch every item from a paginated list endpoint by following has_more.
 * e.g. fetchAllPages("/api/applications", "applications")
 * Used where the page needs the whole list at once (dashboard counts, dropdowns).
 */
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

// Jobs and companies are looked up by id in several places (an application only
// stores job_id, a job only stores company_id), so each one is fetched only once.
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
