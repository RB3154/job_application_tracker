# Architecture

How the code is organized: routers, the request flow, the async setup, `main.py`, settings, and what each file contains.

[← Back to the README](../README.md)

---

## Project Architecture

The backend is organized around four primary API resources, plus the shared
lookup lists (locations, work modes, skills, education requirements, sources):

```text
Client
   |
   v
FastAPI Application
   |
   +-------------------+
   |                   |
   v                   v
Routers             Exception Handlers
   |
   +-----------+-----------+-----------+-----------+
   |           |           |           |           |
   v           v           v           v           v
Companies    Jobs     Applications   Users    Lookup lists
   |           |           |           |           |
   +-----------+-----------+-----------+-----------+
             |
             v
      Async Database Layer
             |
             v
       SQLAlchemy ORM
             |
             v
           asyncpg
             |
             v
        PostgreSQL
```

The FastAPI application uses `APIRouter` to organize API endpoints into
resource-specific modules.

The current router structure is:

```text
routers/
├── __init__.py
├── helpers.py
├── companies.py
├── jobs.py
├── applications.py
├── users.py
├── lookups.py
└── pages.py
```

Each resource router contains the API endpoints associated with that resource.
`pages.py` contains the HTML pages of the frontend (see [Frontend](frontend.md#frontend)).

Shared database and validation helpers are kept in `routers/helpers.py`.

---

## API Router Architecture

The API routes are separated from the main FastAPI application using
FastAPI's `APIRouter`.

### Company Router

```text
routers/companies.py
```

Contains all company CRUD endpoints, the company search, and the company
locations endpoints.

### Job Router

```text
routers/jobs.py
```

Contains all job CRUD endpoints, the job search and filters, and the job
details endpoints (locations, work modes, skills, education, sources).

### Application Router

```text
routers/applications.py
```

Contains all application CRUD endpoints and the status history endpoint.
Status changes are recorded in `save_application_changes()`, which PUT and
PATCH share.

### Lookup Router

```text
routers/lookups.py
```

The five lookup lists work the same way, so `create_lookup_router()` builds
the list/create/rename/delete routes for one list and is called once per list.

### User Router

```text
routers/users.py
```

Contains registration, login (`/token`), forgot/reset password
(`/forgot-password`, `/reset-password`), the logged-in user's account
endpoints (`/me`, including `/me/password`), and logout/session for the login cookie.

### Shared Router Helpers

```text
routers/helpers.py
```

Contains shared asynchronous database and validation helpers used by the
resource routers.

Examples include:

- Resource lookup helpers (application lookup is scoped to the logged-in user)
- `get_job_with_details_or_404()`: a job with its company, locations, skills,
  etc. loaded (used by the API and the job page)
- Ownership: every `get_..._or_404()` and filter helper takes the user id;
  someone else's row is `404`
- `paginate()`: one page of any query, plus the total and `has_more`
- `filter_jobs()`: the job search and filters (used by the API and the jobs page)
- `ensure_ids_exist()`: checks a list of lookup ids before linking them
- Database conflict handling
- Job URL uniqueness validation
- One-application-per-user-per-job validation
- Username and email uniqueness validation

The routers are connected to the FastAPI application through
`app.include_router()`.

The API prefixes are:

```text
/api/companies
/api/jobs
/api/applications
/api/users
/api/locations
/api/work-modes
/api/skills
/api/education
/api/sources
```

Router tags are also used to organize the endpoints in FastAPI's interactive
API documentation.

---

## API Request Flow

A typical API request follows this flow:

```text
Client
   |
   v
FastAPI Application
   |
   v
APIRouter
   |
   v
Route Handler
   |
   v
Pydantic Validation
   |
   v
AsyncSession
   |
   v
SQLAlchemy Async ORM
   |
   v
asyncpg
   |
   v
PostgreSQL
```

---

## Async Architecture

The backend uses SQLAlchemy's asynchronous APIs for PostgreSQL database
operations.

The main async components are:

- `create_async_engine`
- `AsyncSession`
- `async_sessionmaker`
- `asyncpg`
- Async FastAPI route handlers
- Async database dependencies
- Async FastAPI lifespan
- Async database operations

The general database flow is:

```text
Client
   |
   v
FastAPI
   |
   v
Async Route Handler
   |
   v
AsyncSession
   |
   v
SQLAlchemy Async ORM
   |
   v
asyncpg
   |
   v
PostgreSQL
```

### Synchronous → Asynchronous Conversion

The database layer uses the following async equivalents:

```text
Session
   ↓
AsyncSession

create_engine()
   ↓
create_async_engine()

sessionmaker()
   ↓
async_sessionmaker()

PostgreSQL synchronous driver
   ↓
asyncpg
```

Database operations that require asynchronous execution are awaited:

```python
await db.get(...)
await db.execute(...)
await db.commit()
await db.rollback()
await db.refresh(...)
await db.delete(...)
```

Operations that are synchronous remain synchronous.

For example:

```python
db.add(instance)
```

does not require `await`.

---

## Application Entry Point

The FastAPI application is defined in:

```text
main.py
```

`main.py` is responsible for application-level configuration and wiring.

It currently contains:

- FastAPI application creation
- Async lifespan configuration
- Router imports
- Router registration
- The rate limiter (`app.state.limiter` and its `429` handler)
- The `/static` (CSS/JS) and `/media` (uploaded pictures) file mounts
- Exception handlers

The resource-specific API route implementations are kept inside the
corresponding router modules.

The application includes the routers using:

```python
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(applications.router, prefix="/api/applications", tags=["applications"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(lookups.locations_router, prefix="/api/locations", tags=["lookup lists"])
app.include_router(lookups.work_modes_router, prefix="/api/work-modes", tags=["lookup lists"])
app.include_router(lookups.skills_router, prefix="/api/skills", tags=["lookup lists"])
app.include_router(lookups.education_router, prefix="/api/education", tags=["lookup lists"])
app.include_router(lookups.sources_router, prefix="/api/sources", tags=["lookup lists"])
app.include_router(pages.router)
```

This keeps the public API URLs unchanged while separating the internal route
organization. The pages router has no prefix, so its pages live at `/`,
`/jobs`, `/login`, and so on.

---

## FastAPI Lifespan

The application uses FastAPI's lifespan mechanism for startup and shutdown
operations.

The app does **not** create tables on startup. The database schema is owned by
Alembic: run `uv run alembic upgrade head` to create or update the tables
(see [Alembic](#alembic)).

Earlier versions ran `Base.metadata.create_all` on startup. That was removed
because it only creates missing tables (it never changes existing ones), and a
table made by `create_all` is unknown to Alembic, which makes later
migrations fail.

During shutdown, the async SQLAlchemy engine is disposed:

```python
@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()
```

---

## Async Database Sessions

The application creates database sessions using SQLAlchemy's
`async_sessionmaker`.

The FastAPI database dependency provides an `AsyncSession` to API routes.

Conceptually:

```text
Incoming API request
        |
        v
     get_db()
        |
        v
    AsyncSession
        |
        v
     API route
        |
        v
Database operations
        |
        v
   Session closed
```

The async session is managed using an asynchronous context manager so that the
session lifecycle is handled automatically.

---

## Application Settings

Application settings are defined in:

```text
config.py
```

A single `Settings` class (built on `pydantic-settings`) loads values from
`.env` and is exposed as a shared `settings` object:

| Setting | Environment variable | Default |
| --- | --- | --- |
| `database_url` | `DATABASE_URL` | required |
| `secret_key` | `SECRET_KEY` | required, at least 32 characters |
| `algorithm` | `ALGORITHM` | `HS256` |
| `access_token_expire_minutes` | `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |
| `max_upload_size_bytes` | `MAX_UPLOAD_SIZE_BYTES` | `5242880` (5 MB) |
| `items_per_page` | `ITEMS_PER_PAGE` | `10` |
| `reset_token_expire_minutes` | `RESET_TOKEN_EXPIRE_MINUTES` | `60` |
| `mail_server` | `MAIL_SERVER` | `localhost` |
| `mail_port` | `MAIL_PORT` | `587` |
| `mail_username` | `MAIL_USERNAME` | empty |
| `mail_password` | `MAIL_PASSWORD` | empty |
| `mail_from` | `MAIL_FROM` | `noreply@example.com` |
| `mail_use_tls` | `MAIL_USE_TLS` | `true` |
| `frontend_url` | `FRONTEND_URL` | `http://localhost:8000` |
| `cookie_secure` | `COOKIE_SECURE` | `false` (set `true` with HTTPS) |

`secret_key` and `mail_password` are stored as `SecretStr` so they are not
shown in logs or reprs.

`database.py`, `auth.py` and the routers import `settings` from `config.py`.
The routers use `items_per_page` as the default `limit` for list endpoints.

`.env.example` lists every setting with placeholder values. When adding a
setting to `config.py`, add it to both `.env` and `.env.example`.

---

## Project Structure

The current project structure is approximately:

```text
job_application_tracker/
│
├── alembic/
│   ├── versions/
│   │   ├── 09f2cd3da047_initial_schema.py
│   │   ├── 2bc8d0960952_add_users_and_application_ownership.py
│   │   ├── 5c1e7a2f9d34_add_user_password_hash.py
│   │   ├── 8d4b2e6f1a73_add_user_image_file.py
│   │   ├── a3f9c1d7e520_add_password_reset_tokens.py
│   │   ├── 9a7a9755e6a4_add_interview_rounds_to_applications.py
│   │   ├── aeca756ae956_add_created_by_to_company_and_job.py
│   │   ├── fb8f1d0d8193_add_token_version_to_users.py
│   │   ├── a7cf23241ad4_make_username_and_email_unique_ignoring_case.py
│   │   ├── e0b41fa1a607_auto_generate_lookup_table_ids.py
│   │   ├── 8535d075e734_add_application_notes_and_status_history.py
│   │   ├── 5d81e862dbfe_make_job_description_optional.py
│   │   ├── c797f6d44e3b_add_wishlist_application_status.py
│   │   └── 797444886326_make_companies_jobs_and_lists_private.py
│   ├── env.py
│   ├── README
│   └── script.py.mako
│
├── docs/
│   ├── api.md
│   ├── architecture.md
│   ├── auth.md
│   ├── database.md
│   └── frontend.md
│
├── routers/
│   ├── __init__.py
│   ├── helpers.py
│   ├── companies.py
│   ├── jobs.py
│   ├── applications.py
│   ├── users.py
│   ├── lookups.py
│   └── pages.py
│
├── static/
│   ├── css/main.css
│   ├── icons/icon.svg
│   └── js/
│       ├── api.js
│       ├── dashboard.js
│       ├── forms.js
│       ├── pickers.js
│       └── utils.js
│
├── templates/
│   ├── layout.html
│   ├── _macros.html
│   ├── _form_modals.html
│   ├── home.html
│   ├── jobs.html
│   ├── job.html
│   ├── companies.html
│   ├── company.html
│   ├── login.html
│   ├── register.html
│   ├── account.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   └── error.html
│
├── .env
├── .env.example
├── .gitignore
├── .python-version
├── alembic.ini
├── auth.py
├── config.py
├── database.py
├── email_utils.py
├── image_utils.py
├── main.py
├── models.py
├── pyproject.toml
├── rate_limit.py
├── README.md
├── schemas.py
└── uv.lock
```

Local/generated files such as `.venv/`, `__pycache__/`, `.vscode/`, and
uploaded pictures in `media/` may exist locally but are not intended to be committed as application source code.

---

## Project Documentation

### `config.py`

Contains the `pydantic-settings` application settings (database URL, JWT
secret key, algorithm, token lifetime, upload size limit, default page
size, reset token lifetime, and mail server settings).

### `auth.py`

Contains password hashing, JWT access token helpers, password reset token
helpers, and the `get_current_user` dependency.

### `email_utils.py`

Contains `send_email()`, which sends a plain-text email over SMTP with
`aiosmtplib`, and `send_password_reset_email()`, which builds the reset email
(run as a background task by `POST /api/users/forgot-password`) and logs a
clear message if it can't be sent.

### `rate_limit.py`

Contains the shared `slowapi` limiter and the handler that turns "too many
requests" into a `429` JSON error (see [Rate Limiting](auth.md#rate-limiting)).

### `image_utils.py`

Contains the profile picture helpers: cropping and resizing an upload to a
300x300 JPEG with Pillow, saving it to `media/profile_pics/`, and deleting it.

### `database.py`

Contains the asynchronous PostgreSQL and SQLAlchemy database configuration.

### `models.py`

Contains SQLAlchemy ORM models.

### `schemas.py`

Contains Pydantic request and response schemas.

### `main.py`

Contains the FastAPI application, lifespan configuration, router registration,
the rate limiter setup, the `/media` static files mount for profile pictures,
and application-level exception handlers.

### `routers/`

Contains the resource-specific API routers and shared router helpers.

### `alembic/`

Contains database migration configuration and migration revisions.
