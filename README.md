# Job Application Tracker

A backend REST API for managing job applications, companies, and job postings.

This project is being built incrementally while learning and applying modern
Python backend development concepts with FastAPI, Pydantic, SQLAlchemy,
PostgreSQL, and Alembic.

The project started alongside Corey Schafer's FastAPI tutorial and has
progressively been adapted into an application-specific backend with its own
database schema, ORM models, validation rules, and CRUD API.

---

## Features

### Company Management

CRUD operations for companies:

- Create a company
- Retrieve all companies
- Retrieve a company by ID
- Replace a company using PUT
- Partially update a company using PATCH
- Delete a company

### Job Management

CRUD operations for job postings:

- Create a job
- Retrieve all jobs
- Retrieve a job by ID
- Replace a job using PUT
- Partially update a job using PATCH
- Delete a job

Jobs include information such as:

- Role
- Job description
- Job URL
- Posting date
- Application deadline
- Minimum and maximum experience
- Salary information
- Company

### Application Management

CRUD operations for job applications:

- Create an application
- Retrieve all applications
- Retrieve an application by ID
- Replace an application using PUT
- Partially update an application using PATCH
- Delete an application

Applications track:

- Job
- Date applied
- Current application status

Supported application statuses:

Applied
Screening
Interview
Rejected
Offer
Accepted
Withdrawn


---

## Technology Stack

| Technology        | Purpose                                   |
| ----------------- | ----------------------------------------- |
| Python 3.11+      | Programming language                      |
| FastAPI           | REST API framework                        |
| Uvicorn           | ASGI server                               |
| Pydantic          | Request/response validation               |
| SQLAlchemy 2.x    | ORM and database interaction              |
| PostgreSQL        | Relational database                       |
| psycopg           | PostgreSQL database driver                |
| Alembic           | Database migrations                       |
| pydantic-settings | Environment configuration                 |
| uv                | Python package and environment management |

---

## Architecture

The current backend follows this general flow:

```text
Client
   |
   v
FastAPI
   |
   v
Pydantic Schemas
   |
   v
API Route
   |
   v
SQLAlchemy ORM
   |
   v
PostgreSQL
```

Database schema changes are managed separately through:

```text
SQLAlchemy Models
       |
       v
     Alembic
       |
       v
  PostgreSQL Schema
```

---

## Project Structure

```text
job_application_tracker/
│
├── alembic/
│   ├── versions/
│   │   └── 09f2cd3da047_initial_schema.py
│   ├── env.py
│   ├── README
│   └── script.py.mako
│
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

Local/generated files such as `.venv/`, `__pycache__/`, and `.vscode/` may
exist locally but are not intended to be committed as application source code.

---

## Application Entry Point

The FastAPI application is defined in:

```text
main.py
```

Run the application with:

```bash
uv sync
uv run uvicorn main:app --reload
```

The application will be available at:

```text
http://127.0.0.1:8000
```

Interactive Swagger API documentation:

```text
http://127.0.0.1:8000/docs
```

OpenAPI documentation:

```text
http://127.0.0.1:8000/openapi.json
```

---

## API Endpoints

The API is organized around three primary resources.

### Companies

```text
GET     /api/companies
POST    /api/companies
GET     /api/companies/{company_id}
PUT     /api/companies/{company_id}
PATCH   /api/companies/{company_id}
DELETE  /api/companies/{company_id}
```

### Jobs

```text
GET     /api/jobs
POST    /api/jobs
GET     /api/jobs/{job_id}
PUT     /api/jobs/{job_id}
PATCH   /api/jobs/{job_id}
DELETE  /api/jobs/{job_id}
```

### Applications

```text
GET     /api/applications
POST    /api/applications
GET     /api/applications/{application_id}
PUT     /api/applications/{application_id}
PATCH   /api/applications/{application_id}
DELETE  /api/applications/{application_id}
```

---

## PUT vs PATCH

The API distinguishes between full replacement and partial updates.

### PUT

PUT performs a full replacement of the updateable fields.

Example:

```text
PUT /api/companies/COMP1
```

The complete update payload is expected.

### PATCH

PATCH performs a partial update.

Only fields included in the request are changed.

For example:

```text
PATCH /api/companies/COMP1
```

with:

```json
{
    "company_name": "Google India"
}
```

changes only the company name.

The implementation uses:

```python
model_dump(exclude_unset=True)
```

for PATCH requests so omitted fields are not overwritten.

---

## Database

The application uses PostgreSQL as its database.

The database connection is configured through the environment:

```text
DATABASE_URL
```

The value is loaded from `.env` using `pydantic-settings`.

The SQLAlchemy database configuration is located in:

```text
database.py
```

The database layer provides:

* PostgreSQL engine
* SQLAlchemy session factory
* Declarative ORM base
* FastAPI database-session dependency

The PostgreSQL driver used by SQLAlchemy is:

```text
psycopg
```

---

## SQLAlchemy ORM

The ORM models are defined in:

```text
models.py
```

The project uses SQLAlchemy 2.x style declarations including:

```python
Mapped
mapped_column
relationship
```

The ORM layer represents the application's relational database design.

---

## Database Schema

The database currently contains 14 tables:

```text
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

The main entities are:

```text
Company
   |
   | 1-to-many
   v
 Job
   |
   | 1-to-zero-or-one
   v
Application
```

Jobs also have many-to-many relationships with:

* Locations
* Work modes
* Skills
* Education requirements
* Sources

Companies have a many-to-many relationship with locations.

The many-to-many relationships are represented using explicit junction
tables.

---

## Database Constraints

The database schema contains relational constraints such as:

* Primary keys
* Foreign keys
* Unique constraints
* Composite primary keys
* Check constraints
* NOT NULL constraints
* Default values
* Indexes

Examples include:

### Job constraints

```text
application_deadline >= job_posting_date
exp_min >= 0
exp_max >= 0
exp_max >= exp_min
salary_min >= 0
salary_max >= 0
salary_max >= salary_min
```

`job_url` is unique.

### Application constraints

Each job can have at most one application.

Application status is restricted to:

```text
Applied
Screening
Interview
Rejected
Offer
Accepted
Withdrawn
```

Foreign-key relationships are also validated before creating or updating
dependent records.

---

## Pydantic Schemas

Request and response schemas are defined in:

```text
schemas.py
```

Current schemas include:

### Company

```text
CompanyBase
CompanyCreate
CompanyResponse
CompanyUpdate
```

### Job

```text
JobBase
JobCreate
JobResponse
JobUpdate
```

### Application

```text
ApplicationBase
ApplicationCreate
ApplicationResponse
ApplicationReplace
ApplicationUpdate
```

Pydantic is responsible for validating API input before it reaches the
database.

For example, job schemas validate:

* Required fields
* String lengths
* Non-negative experience values
* Non-negative salary values
* Valid date ranges
* Valid salary ranges
* Valid experience ranges
* Valid application statuses

---

## Pydantic and SQLAlchemy Integration

Response schemas use:

```python
model_config = ConfigDict(from_attributes=True)
```

This allows Pydantic response models to be created from SQLAlchemy ORM
objects.

The general flow is:

```text
PostgreSQL
    |
    v
SQLAlchemy ORM object
    |
    v
Pydantic Response Schema
    |
    v
JSON response
```

---

## API Error Handling

The API handles common error conditions including:

* Resource not found
* Duplicate IDs
* Duplicate job URLs
* Duplicate applications for the same job
* Invalid foreign-key references
* Database constraint conflicts
* Invalid request data

HTTP status codes are used to communicate errors.

Examples:

```text
201 Created
204 No Content
404 Not Found
409 Conflict
422 Unprocessable Content
```

Database `IntegrityError` exceptions are handled and converted into
appropriate API conflict responses.

---

## Alembic

Alembic is used for database schema migrations.

The initial migration is:

```text
Revision: 09f2cd3da047
Message: initial schema
```

Apply migrations with:

```bash
uv run alembic upgrade head
```

Check the current migration:

```bash
uv run alembic current
```

Create a new migration after making approved model changes:

```bash
uv run alembic revision --autogenerate -m "description"
```

Generated migrations should always be reviewed before applying them.

Database schema changes should be managed through Alembic rather than using:

```python
Base.metadata.create_all()
```

---

## Database Creation

The PostgreSQL database creation script is provided in:

```text
create_db.sql
```

It contains the SQL required to create the application database.

The database schema itself is managed through SQLAlchemy models and Alembic
migrations.

---

## Configuration

Create a `.env` file containing the PostgreSQL connection URL.

Example:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/job_application_tracker
```

Do not commit `.env` or database credentials to GitHub.

---

## Running the Project

### 1. Install dependencies

```bash
uv sync
```

### 2. Configure PostgreSQL

Create the PostgreSQL database and configure:

```text
DATABASE_URL
```

inside `.env`.

### 3. Apply migrations

```bash
uv run alembic upgrade head
```

### 4. Start FastAPI

```bash
uv run uvicorn main:app --reload
```

### 5. Open Swagger

```text
http://127.0.0.1:8000/docs
```

---

## Current CRUD Implementation

The current API implements CRUD for the three primary entities:

```text
Company
   ├── Create
   ├── Read
   ├── Update
   └── Delete

Job
   ├── Create
   ├── Read
   ├── Update
   └── Delete

Application
   ├── Create
   ├── Read
   ├── Update
   └── Delete
```

Both full replacement and partial update operations are supported.

The implementation also respects the existing relational constraints instead
of bypassing them through application shortcuts.

---

## Development Approach

This project is being developed incrementally.

The learning and implementation process follows:

```text
Learn FastAPI concept
        ↓
Understand the concept
        ↓
Adapt it to the Job Application Tracker
        ↓
Implement it using the project's schema
        ↓
Test the implementation
        ↓
Move to the next concept
```

The goal is not simply to reproduce a tutorial application.

The goal is to understand the underlying backend concepts and apply them to
an application with its own database design and requirements.

---

## Learning Reference

The initial FastAPI learning structure and CRUD concepts were learned while
following **Corey Schafer's FastAPI tutorial**.

Corey Schafer's tutorial served as the learning reference for understanding
core FastAPI concepts and CRUD patterns.

The implementation in this repository has subsequently been adapted into the
Job Application Tracker's own architecture.

The project now uses its own:

* PostgreSQL database
* Relational schema
* SQLAlchemy ORM models
* Pydantic schemas
* Alembic migrations
* API routes
* Validation rules
* Database constraints

Corey Schafer:

[https://www.youtube.com/@coreyms](https://www.youtube.com/@coreyms)

FastAPI tutorial playlist:

[https://www.youtube.com/playlist?list=PL-osiE80TeTs4UjLw5MM6bV2T6a0cBqXH](https://www.youtube.com/playlist?list=PL-osiE80TeTs4UjLw5MM6bV2T6a0cBqXH)

> Note: The tutorial is credited as the learning reference. This repository
> is being progressively adapted into an application-specific backend rather
> than remaining a direct copy of the tutorial project.

---

## Project Documentation

### `FINAL_SCHEMA.md`

The authoritative specification for the database schema.

It defines:

* Tables
* Columns
* Data types
* Nullability
* Primary keys
* Foreign keys
* Unique constraints
* Check constraints
* Defaults
* Indexes
* Relationships

### `CODING_INSTRUCTIONS.md`

Contains project-specific development and implementation rules.

### `create_db.sql`

Contains the PostgreSQL database creation SQL.

### `database.py`

Contains PostgreSQL and SQLAlchemy database configuration.

### `models.py`

Contains SQLAlchemy ORM models.

### `schemas.py`

Contains Pydantic request and response schemas.

### `main.py`

Contains the FastAPI application and current CRUD API endpoints.

---

## Current Limitations

The current implementation focuses on the backend CRUD foundation.

The following features are not implemented yet:

* Authentication
* Authorization
* Dashboard
* Search and filtering
* Advanced application workflows
* Background jobs
* Caching
* Notifications
* Deployment configuration
* Frontend UI

These features can be added incrementally after the backend foundation is
expanded.

---

## Roadmap

Planned development direction:

```text
Current
  ↓
CRUD foundation
  ↓
API organization with routers
  ↓
Reference-table CRUD
  ↓
Junction-table operations
  ↓
Search and filtering
  ↓
Application workflows
  ↓
Authentication & authorization
  ↓
Dashboard / analytics
  ↓
Production backend improvements
  ↓
Deployment
```

The exact implementation order may evolve as the project develops.

---

## Project Goal

The long-term goal is to turn this into a practical Job Application Tracker
while using the project as a hands-on backend engineering learning platform.

The project is intended to provide practical experience with:

* REST API design
* FastAPI
* Pydantic validation
* SQLAlchemy ORM
* PostgreSQL
* Relational database design
* Foreign keys and constraints
* Database migrations
* CRUD operations
* Error handling
* API documentation
* Backend architecture
* Production-oriented development practices

---

## License

This project is currently a personal learning and development project.



### One important thing I changed 🧹

I **didn't carry over the old claims about Jinja2, `templates/`, `static/`, or the home route**, because those belong to the old tutorial-derived frontend setup, not the backend direction you're taking now.

I also deliberately credited **Corey Schafer as the learning reference**, rather than making the README sound like the entire project is his code. That's a much better representation of what you're actually doing: **learn the concept from Corey → understand it → adapt it to your own JAT architecture.** 🚀

One thing to double-check before committing: your `pyproject.toml` still lists `jinja2` and `python-multipart`. Since you've now removed the template/static layer, those may be leftover dependencies and are worth cleaning up separately rather than pretending they're part of the current backend stack.

