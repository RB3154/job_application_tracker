# Frontend

The Jinja2 + JavaScript pages: what each page does, how pages get their data, login in the browser, and the frontend files.

[← Back to the README](../README.md)

---

## Frontend

The app includes a browser frontend built the same way as in Corey Schafer's
tutorial: **Jinja2 templates** rendered by FastAPI, plus **plain JavaScript**
that calls the existing `/api/...` endpoints with `fetch()`. There is no
separate frontend framework or build step.

### Pages

| URL | Page | Login needed |
| --- | --- | --- |
| `/` | **My applications** (the dashboard): your application counts, a **Needs attention** panel, status filters, search, and a **Table** or **Board** view where you change status. Shows a welcome page when logged out. | For the dashboard |
| `/jobs` | Jobs, newest first, with search, location/skill/work mode filters, and **Load more** | Yes |
| `/jobs/{job_id}` | Job details, skills, education, description, and your application (**Track this job** button, notes, status history) | Yes |
| `/companies` | Companies, A to Z, with search and **Load more** | Yes |
| `/companies/{company_id}` | Company details, locations, and its jobs | Yes |
| `/login`, `/register` | Log in / create an account | No |
| `/account` | Profile, profile picture, password, log out, delete account | Yes |
| `/forgot-password`, `/reset-password` | Password reset (the emailed link opens `/reset-password?token=...`) | No |

Logged-in users also get an **Add** menu in the navbar to add an
**application** (the one-step form: company, role, link, status, date, notes;
see [Adding an Application in One Step](api.md#adding-an-application-in-one-step)),
a job, or a company. The **Add application** button on My applications opens
the same form. On your job and company pages you also get **Edit** / **Delete**, plus **Skills & locations** on a
job and **Locations** on a company. Those open pickers where you choose from
your lists as you type, or type a new name to add it.

The jobs and companies filters are plain GET forms, so the filters end up in
the address (`/jobs?skill_id=7&open_only=true`) and can be bookmarked.

### Two ways a page gets its data

```text
Jobs, companies (your own)             Private data (dashboard, account)

Browser -> GET /jobs                   Browser -> GET /
            |                                       |
            v                                       v
routers/pages.py queries the DB        routers/pages.py returns the HTML only
and fills in templates/jobs.html                    |
            |                                       v
            v                          JavaScript calls GET /api/applications
HTML page with the jobs already in it  with "Authorization: Bearer <token>"
                                                    |
                                                    v
                                       JavaScript draws the table
```

The login token is saved in the browser's `localStorage`, not in a cookie, so
the browser does not send it when it asks for a page. That is why pages with
private data load it with JavaScript after the page opens.

**Load more** works like the tutorial's: the server renders the first page
(`ITEMS_PER_PAGE` items) in the same order as the API, then the button calls
`/api/jobs?skip=...&limit=...` for the next items, passing along the filters
from the page's own address.

### My applications: table, board and "Needs attention"

The dashboard's JavaScript lives in `static/js/dashboard.js`.

- **Table / Board toggle**: the choice is remembered in the browser
  (`localStorage`). Both views show the same applications (the status filter
  and the search box apply to both).
- **Board**: columns Wishlist, Applied, Screening, Interview, Offer, and a
  folded **Closed** column (Accepted, Rejected, Withdrawn). Each card shows the
  role, company, date, interview rounds, a notes icon, and a deadline badge for
  Wishlist items. A card moves to another column by picking a new status in
  its dropdown (no drag-and-drop yet; the dropdown also works with a keyboard
  and on phones).
- **Needs attention** (hidden when empty):
  - Wishlist jobs whose deadline is within 7 days or has passed
  - Applications still in Applied with no status change for 14+ days, using
    `last_status_change` from `GET /api/applications`
  The limits are `DEADLINE_WARNING_DAYS` and `FOLLOW_UP_AFTER_DAYS` at the top
  of `dashboard.js`.

The dashboard needs *every* application to count them, so it follows
`has_more` and fetches all pages (100 at a time) instead of only the first.

### Login in the browser

```text
/login form  ->  POST /api/users/token (form data)  ->  access token
        |
        v
token saved in localStorage
        |
        v
every API call adds "Authorization: Bearer <token>"
        |
        v
401 (token expired)  ->  token removed  ->  /login?next=<page you were on>
```

The login response also sets the same token as an **HttpOnly cookie**
(`access_token`). The browser sends it with every page request, so page routes
know who is logged in and send logged-out visitors to `/login?next=...`. Only
page routes read the cookie; the API keeps requiring the `Authorization`
header (see [Login cookie](auth.md#login-cookie-for-pages)).

- **Logging out** calls `POST /api/users/logout` (clears the cookie) and then
  removes the token from `localStorage` (`endSession()` in `api.js`).
- **Browsers that logged in before the cookie existed** have a token but no
  cookie. When such a browser opens `/login`, the page sends its token to
  `POST /api/users/session`, which sets the cookie, and then continues to the
  `next` page; otherwise the two pages would keep sending it back and forth.
- The navbar links (My applications, Jobs, Companies) only appear when logged
  in.

After logging in, you are sent back to the `next` page. Only paths on this site
are accepted, so a link like `?next=https://other-site.com` can't send users
somewhere else. Registering also logs you in automatically.

### Files

```text
routers/pages.py        HTML page routes (hidden from /docs)
templates/
├── layout.html         navbar, footer, theme switch; every page extends it
├── _macros.html        reusable pieces: job card, salary, dates, deadline badge
├── _form_modals.html   New / Edit company and job forms
├── home.html           dashboard / welcome page
├── jobs.html, job.html
├── companies.html, company.html
├── login.html, register.html, account.html
├── forgot_password.html, reset_password.html
└── error.html          HTML error page (404 etc.)
static/
├── css/main.css        colors, dark mode, status badge colors
├── icons/icon.svg      favicon
└── js/
    ├── api.js          token, current user, apiFetch(), fetchAllPages()
    ├── utils.js        escaping, formatting, toasts, confirm dialog
    ├── forms.js        company, job and quick application forms
    ├── dashboard.js    My applications: stats, table, board, needs attention
    └── pickers.js      lookup list pickers (skills, locations, ...)
```

`static/js/api.js` is the only place that talks to the API. Its `apiFetch()`
adds the token, sends plain objects as JSON (and `FormData` as-is for the login
form and picture uploads), handles an expired token, and turns FastAPI's error
body into one readable message. The pages call it instead of repeating that
code.

The JavaScript versions of the formatting helpers (`formatSalary()`,
`deadlineBadge()`, ...) in `utils.js` match the Jinja macros in
`_macros.html`, so cards added by **Load more** look the same as the ones the
server rendered.

### Changes compared to the tutorial's frontend

- A dashboard with counts, status filters, and search, plus inline status and
  interview-round controls
- One shared `apiFetch()` helper instead of the same fetch code in every page
- Returning to the page you came from after logging in (`?next=`)
- Small pop-up toasts instead of success modals you have to close; a toast can
  also be queued to show on the next page after a redirect
- A letter avatar for users without a profile picture, and a **Remove** button
  for the picture
- Dark mode is applied before the page is drawn, so it doesn't flash white
- Dates like `2026-10-29` are read as local dates, so they don't show one day
  early in timezones behind UTC
- Saved links (job URL, company website) only become clickable if they start
  with `http://` or `https://`, so a `javascript:...` URL can't run code
- All text from the API is escaped before it is added to the page, to prevent
  XSS
- Edit / Delete buttons are only shown to users allowed to use them
  (`data-created-by` on the button, checked in `layout.html`)
- Search and filters on the jobs and companies pages
- Pickers for a job's locations, work modes, skills, education and sources
- Application notes and a status history on the job page
