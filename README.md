# Job Application Tracker

A backend REST API for managing job applications, companies, and job postings.

This project is being built incrementally while learning and applying modern
Python backend development concepts with FastAPI, Pydantic, SQLAlchemy,
PostgreSQL, async programming, and Alembic.

The project started alongside Corey Schafer's FastAPI tutorial and has
progressively been adapted into an application-specific backend with its own
database schema, ORM models, validation rules, constraints, and CRUD API.

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

---

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

---

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

```text
Applied
Screening
Interview
Rejected
Offer
Accepted
Withdrawn
```

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
| uv | Python package and environment management |

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

The general request flow is:

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
Async API Route
   |
   v
Async SQLAlchemy ORM
   |
   v
asyncpg
   |
   v
PostgreSQL
```

Database schema changes are managed through Alembic:

```text
SQLAlchemy Models
       |
       v
    Alembic
       |
       v
PostgreSQL Schema
```

The FastAPI application also initializes the SQLAlchemy metadata during
application startup using the async engine.

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

The application uses a FastAPI lifespan function to initialize the database
schema when the application starts and dispose of the async database engine
when the application shuts down.

Start the application with:

```bash
uv run uvicorn main:app --reload
```

The application will be available at:

```text
http://127.0.0.1:8000
```

---

## API Documentation

FastAPI automatically provides interactive API documentation.

### Swagger UI

```text
http://127.0.0.1:8000/docs
```

### ReDoc

```text
http://127.0.0.1:8000/redoc
```

### OpenAPI Schema

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

Example:

```text
PATCH /api/companies/COMP1
```

with:

```json
{
    "company_name": "Google India"
}
```

Only the company name is changed.

The implementation uses:

```python
model_dump(exclude_unset=True)
```

for PATCH requests so omitted fields are not overwritten.

---

## Database

The application uses PostgreSQL as its relational database.

The database connection is configured through:

```text
DATABASE_URL
```

The value is loaded from `.env` using `pydantic-settings`.

The SQLAlchemy database configuration is located in:

```text
database.py
```

The database layer provides:

- Async PostgreSQL engine
- SQLAlchemy `AsyncSession`
- Async session factory
- Declarative ORM base
- Async FastAPI database-session dependency

The PostgreSQL driver used by SQLAlchemy is:

```text
asyncpg
```

The SQLAlchemy connection URL is normalized to use:

```text
postgresql+asyncpg
```

for asynchronous PostgreSQL operations.

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

The async session is managed using an asynchronous context manager so that
the session lifecycle is handled automatically.

---

## FastAPI Lifespan

The application uses FastAPI's lifespan mechanism for startup and shutdown
operations.

During startup:

```text
FastAPI starts
      |
      v
Async database connection
      |
      v
Create SQLAlchemy metadata
```

During shutdown:

```text
FastAPI shuts down
      |
      v
Dispose async SQLAlchemy engine
```

The database initialization uses:

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

The async engine is disposed during shutdown.

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

- Locations
- Work modes
- Skills
- Education requirements
- Sources

Companies have a many-to-many relationship with locations.

The many-to-many relationships are represented using explicit junction tables.

---

## Database Constraints

The database schema contains relational constraints such as:

- Primary keys
- Foreign keys
- Unique constraints
- Composite primary keys
- Check constraints
- NOT NULL constraints
- Default values
- Indexes

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

Examples of validation include:

- Required fields
- String lengths
- Non-negative experience values
- Non-negative salary values
- Valid date ranges
- Valid salary ranges
- Valid experience ranges
- Valid application statuses

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

- Resource not found
- Duplicate IDs
- Duplicate job URLs
- Duplicate applications for the same job
- Invalid foreign-key references
- Database constraint conflicts
- Invalid request data

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

For example, database constraint conflicts can result in:

```text
409 Conflict
```

instead of exposing raw database errors to the API client.

---

## Alembic

Alembic is used for database schema migrations.

The initial migration is:

```text
Revision: 09f2cd3da047
Message: initial schema
```

The Alembic environment has been configured to work with the project's
asynchronous SQLAlchemy engine while using Alembic's migration API.

### Apply migrations

```bash
uv run alembic upgrade head
```

### Check the current migration

```bash
uv run alembic current
```

### Create a new migration

After making approved SQLAlchemy model changes:

```bash
uv run alembic revision --autogenerate -m "description"
```

Generated migrations should always be reviewed before applying them.

---

## Database Creation

The PostgreSQL database creation script is provided in:

```text
create_db.sql
```

It contains the SQL required to create the application database.

The database schema itself is represented through the SQLAlchemy models and
managed through Alembic migrations.

---

## Configuration

Create a `.env` file containing the PostgreSQL connection URL.

Example:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/job_application_tracker
```

The application converts the PostgreSQL URL to the asynchronous SQLAlchemy
driver format internally:

```text
postgresql+asyncpg
```

Do not commit `.env` or database credentials to GitHub.

---

## Installation

This project uses `uv` for Python environment and dependency management.

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

The implementation also respects the existing relational constraints rather
than bypassing them through application shortcuts.

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
core FastAPI concepts and CRUD patterns.

The implementation in this repository has subsequently been adapted into the
Job Application Tracker's own architecture.

The project now uses its own:

- PostgreSQL database
- Relational schema
- SQLAlchemy ORM models
- Pydantic schemas
- Alembic migrations
- Async database layer
- API routes
- Validation rules
- Database constraints

Corey Schafer:

https://www.youtube.com/@coreyms

FastAPI tutorial playlist:

https://www.youtube.com/playlist?list=PL-osiE80TeTs4UjLw5MM6bV2T6a0cBqXH

> Note: The tutorial is credited as the learning reference. This repository
> is being progressively adapted into an application-specific backend rather
> than remaining a direct copy of the tutorial project.

---

## Project Documentation

### `FINAL_SCHEMA.md`

The authoritative specification for the database schema.

It defines:

- Tables
- Columns
- Data types
- Nullability
- Primary keys
- Foreign keys
- Unique constraints
- Check constraints
- Defaults
- Indexes
- Relationships

### `CODING_INSTRUCTIONS.md`

Contains project-specific development and implementation rules.

### `create_db.sql`

Contains the PostgreSQL database creation SQL.

### `database.py`

Contains the asynchronous PostgreSQL and SQLAlchemy database configuration.

### `models.py`

Contains SQLAlchemy ORM models.

### `schemas.py`

Contains Pydantic request and response schemas.

### `main.py`

Contains the FastAPI application, async database operations, validation
logic, error handling, and CRUD API endpoints.

### `alembic/`

Contains database migration configuration and migration revisions.

---

## Current Limitations

The current implementation focuses on the backend CRUD foundation.

The following features are not implemented yet:

- Authentication
- Authorization
- Dashboard
- Search and filtering
- Advanced application workflows
- Background jobs
- Caching
- Notifications
- Deployment configuration
- Frontend UI

These features can be added incrementally after the backend foundation is
expanded.

---

## Roadmap

Planned development direction:

```text
Current
  ↓
Async CRUD Foundation
  ↓
API Organization with Routers
  ↓
Reference-table CRUD
  ↓
Junction-table Operations
  ↓
Search and Filtering
  ↓
Application Workflows
  ↓
Authentication & Authorization
  ↓
Dashboard / Analytics
  ↓
Production Backend Improvements
  ↓
Deployment
```

The exact implementation order may evolve as the project develops.

---

## Project Goal

The long-term goal is to turn this into a practical Job Application Tracker
while using the project as a hands-on backend engineering learning platform.

The project is intended to provide practical experience with:

- REST API design
- FastAPI
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
- Error handling
- API documentation
- Backend architecture
- Production-oriented development practices

---

## License

This project is currently a personal learning and development project.