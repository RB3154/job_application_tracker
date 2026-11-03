# Job Application Tracker

A private, login-only web app for tracking your own job search. Save the jobs you
find, follow each application from **Wishlist** to **Offer**, and see at a glance
which ones need attention. Nobody else can see your data.

Built with **FastAPI**, **PostgreSQL** and a Jinja2 + JavaScript frontend, tested
with **571 automated tests**, and deployed on **AWS** with Docker, HTTPS, automatic
deploys and error monitoring.

**Live:** <https://52-64-121-241.sslip.io> (register an account to try it)

---

## Highlights

- **Private by design**: every company, job, list and application belongs to one
  user. Requests for anyone else's data return `404`, and this is covered by tests.
- **Secure accounts**: Argon2 password hashes, JWT login with an HttpOnly cookie,
  logout of other devices after a password change, rate-limited login and password
  reset, and password reset emails.
- **Async backend**: FastAPI with async SQLAlchemy 2.x and asyncpg, Pydantic
  validation, and a schema owned by Alembic migrations with database constraints.
- **Tested**: 571 pytest tests against a real PostgreSQL test database, with S3 and
  email faked. They run on every push.
- **Production deployment**: a Docker image in ECR, running on EC2 behind Caddy
  (automatic HTTPS), with RDS PostgreSQL, S3 for pictures and Gmail for emails.
- **CI/CD**: GitHub Actions runs ruff and the tests, builds the image, deploys over
  SSH, runs migrations and checks `/health` on every push to `main`.
- **Monitoring**: Sentry error tracking tagged with the running commit, plus Docker
  log limits so the disk can't fill up.

---

## Features

- **Applications**: track each one with a status (Wishlist, Applied, Screening,
  Interview, Offer, Accepted, Rejected, Withdrawn), date, interview rounds, private
  notes and an automatic status history.
- **One-step Add application**: just the company, role and link. The company and
  job are found or created automatically. Optional sections save salary,
  experience, deadline, description and website.
- **Dashboard**: a table or a board with a column per status, stats, search, and a
  "Needs attention" panel for wishlist deadlines and applications waiting too long.
- **Companies and jobs**: your own, with search and filters (text, location,
  skill, work mode).
- **Lookup lists**: locations, work modes, skills (required or nice to have),
  education requirements and sources, picked as you type.
- **Accounts**: register, log in, profile picture (stored in S3), change password,
  and password reset by email.

See [docs/api.md](docs/api.md#features) for every rule in detail.

---

## Architecture

```text
Browser ──HTTPS──► Caddy (TLS, reverse proxy) ──► FastAPI app (Docker, EC2)
                                                    ├──► PostgreSQL (AWS RDS, private)
                                                    ├──► S3 (profile pictures)
                                                    ├──► Gmail SMTP (reset emails)
                                                    └──► Sentry (errors)

git push ──► GitHub Actions: ruff + pytest ──► build image ──► ECR
                                            └──► SSH to EC2: pull, migrate, restart, health check
```

| Layer | How it's built |
| --- | --- |
| API | FastAPI routers per resource (`routers/`), Pydantic schemas, consistent JSON errors |
| Data | Async SQLAlchemy 2.x models, asyncpg, Alembic migrations, constraints in the database |
| Auth | JWT access tokens, an HttpOnly cookie for pages, token versions, slowapi rate limits |
| Frontend | Jinja2 pages and plain JavaScript modules that call the same API |
| Infrastructure | Docker, Caddy, EC2, RDS, S3, ECR, IAM roles (no keys on the server) |

More in [docs/architecture.md](docs/architecture.md).

---

## Tech Stack

| Area | Tools |
| --- | --- |
| Backend | Python 3.11, FastAPI, Uvicorn, Pydantic, pydantic-settings |
| Database | PostgreSQL, SQLAlchemy 2.x (async), asyncpg, Alembic |
| Auth and security | PyJWT, pwdlib (Argon2), slowapi |
| Files and email | boto3 (S3), Pillow, aiosmtplib |
| Frontend | Jinja2, JavaScript, Bootstrap 5, Bootstrap Icons |
| Infrastructure | Docker, Caddy, AWS (EC2, RDS, S3, ECR, IAM), GitHub Actions |
| Monitoring | Sentry |
| Quality | pytest, moto (fake S3), ruff, uv |

---

## Documentation

| File | What's inside |
| --- | --- |
| [docs/api.md](docs/api.md) | Every `/api/...` endpoint: resources and rules, ownership, lookup lists, pagination, filters and errors |
| [docs/architecture.md](docs/architecture.md) | How the code is organized: routers, request flow, async setup and each file |
| [docs/database.md](docs/database.md) | The schema, constraints, models, Pydantic schemas and migrations |
| [docs/auth.md](docs/auth.md) | Login, JWT tokens, logging out other devices, rate limiting and password reset |
| [docs/frontend.md](docs/frontend.md) | The pages, how they get their data, and the frontend files |
| [docs/deploy_aws.md](docs/deploy_aws.md) | The full AWS setup: Docker, Caddy and HTTPS, RDS, CI/CD, Sentry, troubleshooting |

While running locally, the interactive API docs are at `/docs` (Swagger UI) and
`/redoc`. They're turned off on the live site.

---

## Running Locally

You need Python 3.11+, [uv](https://docs.astral.sh/uv/) and PostgreSQL.

```bash
uv sync                                # install dependencies
cp .env.example .env                   # then fill in the values (see below)
uv run alembic upgrade head            # create the tables
uv run uvicorn main:app --reload       # start the app
```

Open <http://127.0.0.1:8000> for the app, or <http://127.0.0.1:8000/docs> for Swagger UI.

### Settings

All settings are in [`.env.example`](.env.example). The ones you must fill in:

| Setting | What to put |
| --- | --- |
| `DATABASE_URL` | Your local PostgreSQL database, e.g. `postgresql://postgres:password@localhost:5432/job_application_tracker` |
| `SECRET_KEY` | At least 32 random characters: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `S3_BUCKET_NAME`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | An S3 bucket and an IAM user for profile pictures |
| `MAIL_*` | SMTP details. A free [Mailtrap](https://mailtrap.io) sandbox is easiest while developing, because it catches every email |

The S3 bucket needs two permissions on its `profile_pics/` folder:
[`deploy/s3-bucket-policy.json`](deploy/s3-bucket-policy.json) (anyone can view
pictures) and [`deploy/iam-policy-server-s3.json`](deploy/iam-policy-server-s3.json)
(the app can upload and delete them).

Never commit `.env`, database passwords or AWS keys.

### Tests and Linting

```bash
uv run pytest              # 571 tests
uv run ruff check          # lint
uv run ruff format         # format
```

The tests need an empty database named after yours plus `_test`, created once:

```sql
CREATE DATABASE job_application_tracker_test;
```

They never touch your real database, S3 bucket or inbox: S3 and email are faked,
and `tests/conftest.py` refuses to run on a database whose name doesn't end in `_test`.

---

## Deployment

The live site runs on AWS, and every push to `main` deploys automatically:

1. **GitHub Actions** runs ruff and the full test suite on a throwaway PostgreSQL database.
2. If they pass, it builds the Docker image and pushes it to **ECR**, tagged with the commit.
3. It connects to **EC2** over SSH and runs [`deploy/update.sh`](deploy/update.sh),
   which pulls the image, runs `alembic upgrade head`, restarts the app behind
   Caddy and waits for `/health`.

If a test fails, nothing is deployed. The step-by-step setup, from an empty AWS
account to a live HTTPS site, is in [docs/deploy_aws.md](docs/deploy_aws.md).

---

## Roadmap

- [x] Async CRUD API with routers, validation and database constraints
- [x] Users, JWT login, ownership and protected routes
- [x] Profile pictures (S3), pagination, password reset emails
- [x] Alembic-owned schema
- [x] Jinja2 + JavaScript frontend
- [x] Security hardening: token versions, rate limiting
- [x] Lookup lists, search and filters, notes and status history
- [x] Tracker redesign: Add application form, Wishlist, board, Needs attention
- [x] Private per-user data and login-only pages
- [x] Automated tests (pytest)
- [x] Docker and AWS deployment with HTTPS
- [x] CI/CD with GitHub Actions, and Sentry monitoring
- [ ] Analytics: an Insights page with charts of your job search
- [ ] Reminders for deadlines and follow-ups

**Known limitations:** rate limit counts live in memory (one server process), and
emails use FastAPI's in-process `BackgroundTasks` rather than a job queue. Both are
fine for one server, and would move to Redis to scale out.

---

## Learning Reference

This project started alongside **Corey Schafer's FastAPI tutorial**
([channel](https://www.youtube.com/@coreyms),
[playlist](https://www.youtube.com/playlist?list=PL-osiE80TeTs4UjLw5MM6bV2T6a0cBqXH)),
which taught the core concepts: async CRUD, routers, JWT login, uploads,
pagination, password reset, Alembic and a Jinja2 frontend.

It has since become its own application, with its own schema, models, validation
rules and features. Added beyond the tutorial:

- Fully private per-user data and login-only pages
- Logging out other devices after a password change (token versions)
- Rate limiting, and case-insensitive unique usernames and emails
- Lookup lists, search and filters, notes and status history
- The Wishlist status, board view, Needs attention panel and one-step Add application form
- 571 tests, Docker, AWS deployment with Caddy HTTPS, CI/CD and Sentry

---

## License

A personal learning project by [Rudra Bhardwaj](https://github.com/RB3154).
