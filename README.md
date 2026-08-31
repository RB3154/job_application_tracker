# Job Application Tracker

A personal Job Application Tracker being built with FastAPI and
PostgreSQL. The project is developed incrementally while learning
FastAPI concepts, with tutorial material progressively adapted into an
application-specific architecture.

## Current Status

The database and model foundation is implemented and the initial schema
migration has been applied successfully.

### Implemented

-   FastAPI application with a Job Application Tracker home route
-   Jinja2 template configuration and static-file mounting
-   HTML and JSON-oriented exception handling
-   PostgreSQL connection configuration loaded from `.env`
-   SQLAlchemy 2.x ORM models for the tracker schema
-   Core Pydantic schemas for `Company`, `Job`, and `Application`
-   Alembic configuration and an applied initial migration
-   PostgreSQL database with the 14-table application schema

The current application does **not** yet include CRUD operations, job
API endpoints, routers, authentication, or a database-backed dashboard.

The `templates/` and `static/` directories are retained from the
learning/reference implementation and will be tailored to the Job
Application Tracker as development progresses.

## Technology Stack

-   Python 3.11+
-   FastAPI
-   Uvicorn
-   Jinja2
-   PostgreSQL
-   SQLAlchemy 2.x
-   psycopg
-   Pydantic
-   pydantic-settings
-   Alembic
-   uv

## Project Structure

``` text
job_application_tracker/
├── alembic/
│   ├── versions/
│   │   └── 09f2cd3da047_initial_schema.py
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── static/
├── templates/
├── .env
├── .gitignore
├── .python-version
├── alembic.ini
├── CODING_INSTRUCTIONS.md
├── create_db.sql
├── database.py
├── FINAL_SCHEMA.md
├── main.py
├── models.py
├── pyproject.toml
├── README.md
├── schemas.py
└── uv.lock
```

Local/generated files such as `.venv/`, `__pycache__/`, and `.vscode/`
may exist in the workspace but are not source files intended for the
repository.

## Application Entry Point

Run:

``` bash
uv sync
uv run uvicorn main:app --reload
```

Application: `http://127.0.0.1:8000`

FastAPI docs: `http://127.0.0.1:8000/docs`

Current implemented route:

``` text
GET /
```

`main.py` mounts static files at `/static` and configures Jinja2
templates from `templates/`. The previous in-memory post/blog data and
`/posts` / `/api/posts` routes are no longer part of the application.

## Database and ORM

`database.py` loads `DATABASE_URL` from `.env` and configures a
PostgreSQL SQLAlchemy engine using the psycopg driver. It also provides
the declarative `Base`, session factory, and FastAPI-ready
database-session dependency.

`models.py` defines the SQLAlchemy 2.x ORM layer.

The current database schema contains these 14 application tables:

``` text
application
company
company_location
education_requirement
job
job_education
job_location
job_skill
job_source
job_work_mode
location
skill
source
work_mode
```

`FINAL_SCHEMA.md` is the authoritative specification for these tables,
including columns, relationships, constraints, defaults, and indexes.

## PostgreSQL Database Creation

`create_db.sql` contains the SQL used to create the PostgreSQL database:

``` sql
CREATE DATABASE job_application_tracker;
```

The application schema is managed through SQLAlchemy models and Alembic
migrations.

## Pydantic Schemas

`schemas.py` currently contains:

-   `CompanyBase`, `CompanyCreate`, `CompanyResponse`
-   `JobBase`, `JobCreate`, `JobResponse`
-   `ApplicationBase`, `ApplicationCreate`, `ApplicationResponse`

Response schemas use `from_attributes=True` so they can later be
populated from SQLAlchemy model instances.

These schemas are defined but are not yet connected to CRUD operations
or database-backed API endpoints.

## Alembic Migrations

The initial migration has been applied to the configured PostgreSQL
database:

``` text
Revision: 09f2cd3da047
Message: initial schema
Status: head
```

Commands:

``` bash
uv run alembic upgrade head
uv run alembic current
```

Database schema changes should be managed through reviewed Alembic
migrations rather than `Base.metadata.create_all()`.

## Supporting Files

-   `.env` - Local PostgreSQL configuration; do not commit secrets.
-   `.gitignore` - Excludes local/generated files and environment
    secrets from Git.
-   `.python-version` - Specifies the project's Python version.
-   `alembic.ini` - Alembic configuration.
-   `CODING_INSTRUCTIONS.md` - Project implementation guidance.
-   `create_db.sql` - PostgreSQL database creation script.
-   `FINAL_SCHEMA.md` - Authoritative database schema specification.
-   `pyproject.toml` - Project configuration and dependencies.
-   `uv.lock` - Locked dependency versions.

## Planned Next Steps

The following are planned and are not implemented yet:

-   CRUD operations for jobs, companies, and applications
-   Database-backed API endpoints
-   FastAPI route organization with routers
-   Connecting templates to persisted data
-   Search and filtering
-   Application-status workflows
-   Authentication and authorization
-   Dashboard statistics
-   Additional ATS-style features

## Development Approach

The project is being built alongside Corey Schafer's FastAPI tutorial
rather than attempting to implement the entire application at once.

``` text
FastAPI Tutorial Concept
        ↓
Understand the concept
        ↓
Adapt it to Job Application Tracker
        ↓
Implement it in the project
        ↓
Move to the next concept
```

The goal is to learn each FastAPI concept and immediately apply it to
the Job Application Tracker.

## Learning Reference

Corey Schafer's FastAPI tutorial series is the learning reference for
this project. Existing `templates/` and `static/` assets, along with
parts of the initial FastAPI structure, originated from or were adapted
while following the tutorial.

The project is progressively being reshaped into an independent Job
Application Tracker with its own PostgreSQL schema, SQLAlchemy ORM
models, Pydantic schemas, Alembic migrations, and planned application
features.
