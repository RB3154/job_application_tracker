# Job Application Tracker

A private, login-only tracker for your own job applications: log in, record
where you applied, and follow each application from Wishlist to Offer. Nobody
else can see your data. It is a FastAPI REST API with a browser frontend
(Jinja2 templates + JavaScript) built on top of it.

This project is being built incrementally while learning and applying modern
Python backend development concepts with FastAPI, Pydantic, SQLAlchemy,
PostgreSQL, async programming, API routers, and Alembic.

The project started alongside Corey Schafer's FastAPI tutorial and has
progressively been adapted into an application-specific backend with its own
database schema, ORM models, validation rules, constraints, async database
layer, and CRUD API.

---

## Features

- **Private**: log in to use it; your companies, jobs, lists and applications
  are visible only to you.
- **Companies and jobs**: your own, with search and filters
  (text, location, skill, work mode).
- **Lookup lists**: locations, work modes, skills (required or nice to have),
  education requirements and sources, picked as you type and attached to jobs
  and companies.
- **Applications**: each user tracks their own, with a status (Wishlist,
  Applied, Screening, Interview, Offer, Accepted, Rejected, Withdrawn), date,
  interview rounds, private notes, and an automatic status history.
- **Add application**: one form needs just the company, role and link; the
  company and job are found or created automatically. Optional, folded
  "Job details" and "Company details" sections save salary, experience,
  deadline, description and website too, if you want.
- **Accounts**: register, log in (JWT), profile picture, change password
  (logs out other devices), and password reset by email.
- **Security**: Argon2 password hashes, rate-limited login and password reset,
  case-insensitive unique usernames and emails, an HttpOnly login cookie for
  pages, and every request limited to your own data (anyone else's is `404`).
- **Dashboard**: a table or a board with a column per status, and a "Needs
  attention" panel for wishlist deadlines and applications waiting too long
  for news.
- **Frontend**: Jinja2 pages with plain JavaScript (dashboard, jobs, companies,
  account) built on top of the same API.

See [docs/api.md](docs/api.md#features) for every rule in detail.

---

## Documentation

The details live in `docs/`:

| File | What's inside |
| --- | --- |
| [docs/api.md](docs/api.md) | Everything the `/api/...` endpoints do: resources and their rules, every endpoint, ownership, lookup lists, pagination, search and filters, PUT vs PATCH, and errors. |
| [docs/architecture.md](docs/architecture.md) | How the code is organized: routers, the request flow, the async setup, `main.py`, settings, and what each file contains. |
| [docs/database.md](docs/database.md) | The PostgreSQL schema, its constraints, the SQLAlchemy models and Pydantic schemas, and the Alembic migrations. |
| [docs/deploy_aws.md](docs/deploy_aws.md) | Running the app on AWS with Docker: ECR, EC2, RDS, updates and troubleshooting. |
| [docs/auth.md](docs/auth.md) | Login, JWT tokens, logging out other devices, protected routes, rate limiting, and password reset. |
| [docs/frontend.md](docs/frontend.md) | The Jinja2 + JavaScript pages: what each page does, how pages get their data, login in the browser, and the frontend files. |

Interactive API docs are also available while the app runs, at `/docs`
(Swagger UI) and `/redoc`.

---

## Technology Stack

| Technology | Purpose |
| --- | --- |
| Python 3.11+ | Programming language |
| FastAPI | REST API framework |
| Uvicorn | ASGI server |
| Pydantic | Request/response validation |
| SQLAlchemy 2.x | ORM and database interaction |
| PostgreSQL | Relational database |
| asyncpg | Asynchronous PostgreSQL database driver |
| Alembic | Database migrations |
| pydantic-settings | Environment configuration |
| email-validator | Email validation for Pydantic `EmailStr` (via `fastapi[standard]`) |
| PyJWT | JWT access token creation and verification |
| pwdlib (Argon2) | Password hashing |
| Pillow | Profile picture cropping and resizing |
| boto3 | Storing profile pictures in AWS S3 |
| aiosmtplib | Sending password reset emails asynchronously over SMTP |
| slowapi | Rate limiting registration, login and password reset requests |
| uv | Python package and environment management |
| Jinja2 | HTML templates for the frontend pages |
| Bootstrap 5 + Bootstrap Icons | Frontend styling and components (loaded from a CDN) |
| ruff (dev) | Linting and code formatting |
| pytest (dev) | Test runner for the suite in `tests/` |
| moto (dev) | Fake AWS S3 used by the tests |

---

## Configuration

Copy `.env.example` to `.env` in the project root and fill in these values:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/job_application_tracker
SECRET_KEY=<at least 32 random characters>
```

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

The application will not start without a `SECRET_KEY` of at least 32
characters.

Profile pictures are stored in an AWS S3 bucket, so fill in the `S3_*` settings
too. The application will not start without `S3_BUCKET_NAME`:

```env
S3_BUCKET_NAME=<your bucket name>
S3_REGION=<your bucket's region, e.g. ap-southeast-2>
S3_ACCESS_KEY_ID=<from your IAM user>
S3_SECRET_ACCESS_KEY=<from your IAM user>
```

The bucket and IAM user need these permissions on the bucket's `profile_pics/*`
files:

- **Bucket policy**: anyone can view them (`s3:GetObject`), so that browsers can
  load the pictures.
- **IAM user's policy**: the app can upload and delete them (`s3:PutObject`,
  `s3:DeleteObject`).

For password reset emails, fill in the `MAIL_*` settings. While developing, a
free [Mailtrap](https://mailtrap.io) sandbox inbox is the easiest option: it
catches every email so nothing reaches a real inbox. Copy the SMTP host, port,
username, and password from your Mailtrap inbox into `.env`:

```env
MAIL_SERVER=sandbox.smtp.mailtrap.io
MAIL_PORT=2525
MAIL_USERNAME=<from Mailtrap>
MAIL_PASSWORD=<from Mailtrap>
MAIL_FROM=noreply@jobtracker.com
MAIL_USE_TLS=true
```

Without mail settings the app still runs, but sending a reset email fails (the
error is logged by the server after the `202` response has been sent).

The application converts the PostgreSQL URL to the asynchronous SQLAlchemy
driver format internally:

```text
postgresql+asyncpg
```

Do not commit `.env`, database credentials or AWS keys to GitHub.

---

## Installation

This project uses `uv` for Python environment and dependency management.

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure PostgreSQL

Create the PostgreSQL database, copy `.env.example` to `.env` (see [Configuration](#configuration)), and configure:

```text
DATABASE_URL
SECRET_KEY
```

inside `.env`.

### 3. Apply migrations

```bash
uv run alembic upgrade head
```

This step is required: the app does not create tables on startup.

### 4. Start FastAPI

```bash
uv run uvicorn main:app --reload
```

### 5. Open the app

```text
http://127.0.0.1:8000        the frontend
http://127.0.0.1:8000/docs   Swagger UI
```

### Development tools

```bash
uv run ruff check        # find problems (unused imports, long lines, import order, ...)
uv run ruff check --fix  # fix the ones ruff can fix safely
uv run ruff format       # format the code
uv run pytest            # run the tests in tests/
```

The ruff settings are in `pyproject.toml`: 120-character lines, two blank
lines after imports (this project's style), and `alembic/versions` left alone.

The tests need an empty PostgreSQL database, created once. Its name is your
`DATABASE_URL` database name plus `_test`:

```sql
CREATE DATABASE job_application_tracker_test;
```

They never touch your real database, S3 bucket or inbox: S3 and email are
faked, and `tests/conftest.py` refuses to run on a database whose name doesn't
end in `_test`.

---

## Current Limitations

The following are not implemented yet:

- Notes and status history on the dashboard (they are on the job page)
- Rate limit counts shared between server processes (they live in memory,
  see [Rate Limiting](docs/auth.md#rate-limiting))
- A real background job queue (emails use FastAPI's simple in-process
  `BackgroundTasks`)
- Caching
- Notifications and reminders (e.g. for application deadlines)
- Real password reset emails on AWS (the deploy still uses the Mailtrap sandbox, see
  [Deploying to AWS](docs/deploy_aws.md#before-real-use))

These features can be added incrementally as the project grows.

---

## Roadmap

Planned development direction:

```text
Async CRUD Foundation
  ↓
API Organization with Routers
  ↓
Users, Application Ownership & Auth Utilities
  ↓
Login Endpoint & Protected Routes
  ↓
Profile Picture Uploads
  ↓
Pagination
  ↓
Password Reset & Background Tasks
  ↓
Alembic-owned Schema & Autogenerate Workflow
  ↓
Jinja2 + JavaScript Frontend
  ↓
Security Hardening (token versions, rate limiting)
  ↓
Reference-table CRUD & Junction-table Operations
  ↓
Search and Filtering
  ↓
Application Notes & Status History
  ↓
Tracker Redesign (Add application form, Wishlist, board, needs attention)
  ↓
Private Per-user Data & Login-only Pages
  ↓
Automated Tests (pytest)
  ↓
Docker & AWS Deployment                          ← current
  ↓
Analytics
  ↓
Production Backend Improvements
```

Everything up to and including the automated tests is implemented. The Docker
setup is ready, and the AWS steps are in [docs/deploy_aws.md](docs/deploy_aws.md).

The exact implementation order may evolve as the project develops.

---

## Development Approach

This project is being developed incrementally.

The learning and implementation process follows:

```text
Learn FastAPI / Backend Concept
        ↓
Understand the Concept
        ↓
Adapt It to the Job Application Tracker
        ↓
Implement It Using the Project's Schema
        ↓
Test the Implementation
        ↓
Move to the Next Concept
```

The goal is not simply to reproduce a tutorial application.

The goal is to understand the underlying backend concepts and apply them to
an application with its own database design and requirements.

---

## Learning Reference

The initial FastAPI learning structure and CRUD concepts were learned while
following **Corey Schafer's FastAPI tutorial**.

Corey Schafer's tutorial served as the learning reference for understanding
core FastAPI concepts, CRUD patterns, asynchronous architecture, and API
organization.

The implementation in this repository has subsequently been adapted into the
Job Application Tracker's own architecture.

Tutorial topics applied to this project so far (each adapted to this schema):

- CRUD with SQLAlchemy and async database sessions
- API routers
- Users, password hashing, and JWT login
- Ownership checks (`403`) for protected resources
- Profile picture uploads
- Pagination
- Password reset with emails sent through FastAPI `BackgroundTasks`
- PostgreSQL with Alembic as the only owner of the schema, and the
  `alembic revision --autogenerate` workflow (`interview_rounds` column)
- A Jinja2 + JavaScript frontend (see [Frontend](docs/frontend.md#frontend))

Added beyond the tutorial:

- Fully private per-user data and login-only pages (login cookie for pages)
- Logging out other devices after a password change (token versions)
- Rate limiting with `slowapi`
- Case-insensitive unique usernames and emails enforced by the database
- Lookup lists and linking them to jobs and companies
- Search and filters
- Application notes and status history
- A Wishlist status, a board view and a "Needs attention" panel
- A one-step Add application form with optional job and company details
- Linting and formatting with `ruff`

The project now uses its own:

- PostgreSQL database
- Relational schema
- SQLAlchemy ORM models
- Pydantic schemas
- Alembic migrations
- Async database layer
- API routers
- API routes
- Validation rules
- Database constraints
- Application-specific CRUD behavior

Corey Schafer:

https://www.youtube.com/@coreyms

FastAPI tutorial playlist:

https://www.youtube.com/playlist?list=PL-osiE80TeTs4UjLw5MM6bV2T6a0cBqXH

> Note: The tutorial is credited as the learning reference. This repository
> is being progressively adapted into an application-specific backend rather
> than remaining a direct copy of the tutorial project.

---

## Project Goal

The long-term goal is to turn this into a practical Job Application Tracker
while using the project as a hands-on backend engineering learning platform.

The project is intended to provide practical experience with:

- REST API design
- FastAPI
- APIRouter-based API organization
- Async Python
- Pydantic validation
- SQLAlchemy ORM
- Async SQLAlchemy
- PostgreSQL
- asyncpg
- Relational database design
- Foreign keys and constraints
- Database migrations
- CRUD operations
- Pagination, search and filtering
- Password hashing and JWT authentication
- Rate limiting
- Error handling
- API documentation
- Backend architecture
- Production-oriented development practices

---

## License

This project is currently a personal learning and development project.
