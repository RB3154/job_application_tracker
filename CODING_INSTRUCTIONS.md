# CODING INSTRUCTIONS

## 1. Source of Truth

`FINAL_SCHEMA.md` is the authoritative specification for the database schema.

The implementation MUST follow `FINAL_SCHEMA.md`.

Do not independently redesign, simplify, expand, normalize, denormalize, or otherwise modify the database schema.

Do not add, remove, rename, or change:
- Tables
- Columns
- Column names
- Data types
- Nullability
- Primary keys
- Foreign keys
- Unique constraints
- Check constraints
- Default values
- Indexes
- Relationships

unless explicitly instructed by the user.

If `FINAL_SCHEMA.md` conflicts with another instruction or existing code, stop and ask the user for clarification rather than making an assumption.

---

## 2. Project Technology

Use the following technologies for the database implementation:

- Python
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- FastAPI

Do not introduce another ORM or database technology unless explicitly instructed.

---

## 3. Implementation Strategy

Implement the project incrementally.

Do NOT attempt to build the entire application in one step.

Work on one logical component at a time.

Recommended order:

1. Database configuration
2. SQLAlchemy Base
3. Reference/secondary models
4. Main entity models
5. Junction models
6. Relationships
7. Alembic configuration
8. Initial migration
9. Database creation
10. Database testing
11. Application/business logic
12. FastAPI integration

After completing each major component:
- Explain what was implemented.
- List the files created or modified.
- Explain important implementation decisions.
- Report any assumptions.
- Run appropriate tests/checks.
- Stop before beginning the next major component unless instructed to continue.

---

## 4. Database Schema Implementation

Implement the database schema exactly as specified in `FINAL_SCHEMA.md`.

The following must be preserved exactly:

- Table structure
- Column names
- Column types
- NULL/NOT NULL behavior
- Primary keys
- Foreign keys
- Composite primary keys
- Unique constraints
- Check constraints
- Default values
- Indexes
- Relationships

Do not replace a documented design with an alternative design simply because it is considered a common "best practice."

The documented schema takes priority.

---

## 5. IDs

Use the ID data types specified in `FINAL_SCHEMA.md`.

Use `INT` where the schema specifies `INT`.

Do NOT automatically replace `INT` with `BIGINT`.

Do NOT change ID formats without explicit approval.

Primary keys and their corresponding foreign keys must use compatible data types.

---

## 6. SQLAlchemy Models

Use SQLAlchemy 2.x style.

Prefer:
- `Mapped`
- `mapped_column`
- `relationship`

Use explicit table and column definitions.

Ensure SQLAlchemy models accurately represent `FINAL_SCHEMA.md`.

Do not add ORM relationships that are not represented in the documented database design unless explicitly requested.

---

## 7. Foreign Keys and Relationships

Implement every documented foreign key.

Ensure that:
- Referenced tables exist before dependent tables are created.
- FK columns use compatible data types.
- Composite foreign keys are implemented correctly where required.
- Junction tables correctly represent many-to-many relationships.

Do not invent additional relationships.

---

## 8. Junction Tables

Treat junction tables as proper relational tables.

Preserve their documented:
- Composite primary keys
- Foreign keys
- Additional attributes
- Constraints
- Indexes

Do not replace a documented junction table with a SQLAlchemy shortcut such as an automatically generated association table.

---

## 9. Constraints

All constraints documented in `FINAL_SCHEMA.md` must be implemented.

This includes:

- PRIMARY KEY
- FOREIGN KEY
- UNIQUE
- CHECK
- NOT NULL
- DEFAULT

Do not rely on application-level validation when a database-level constraint is explicitly specified in `FINAL_SCHEMA.md`.

Application-level validation may be added in addition to database constraints, but must not replace them.

---

## 10. Indexes

Implement the indexes specified in `FINAL_SCHEMA.md`.

Do not create indexes on arbitrary columns merely because they could potentially be useful.

Do not create duplicate indexes.

Remember that primary keys and unique constraints may already create indexes depending on PostgreSQL behavior.

---

## 11. PostgreSQL

The target database is PostgreSQL.

Use PostgreSQL-compatible SQL and SQLAlchemy configuration.

Do not introduce SQLite-specific behavior.

Do not use SQLite as a substitute for PostgreSQL unless explicitly instructed.

---

## 12. Alembic

Use Alembic for database schema migrations.

Schema changes should be represented through migrations.

Do not manually modify the production/database schema to bypass migrations.

Before generating a migration:
- Review the SQLAlchemy models.
- Compare them against `FINAL_SCHEMA.md`.
- Ensure the migration represents the intended schema.

After generating a migration:
- Review the generated migration.
- Do not blindly assume autogenerated migrations are correct.

---

## 13. Existing Code

Before modifying an existing file:

1. Read the file.
2. Understand its current purpose.
3. Identify existing dependencies.
4. Preserve working functionality.

Do not overwrite an existing file blindly.

Do not remove existing functionality unless explicitly instructed.

---

## 14. Coding Style

Write clear, maintainable code.

Use:
- Type hints
- Descriptive names
- Small and focused functions
- Clear module organization
- Appropriate error handling

Avoid:
- Unnecessary abstractions
- Premature optimization
- Overengineering
- Duplicate code
- Unnecessary dependencies

Prefer simple solutions unless the project requirements require additional complexity.

---

## 15. Validation and Testing

After implementing a database component, verify it.

At minimum, test:

### Valid data
- Valid records can be inserted.
- Valid relationships can be created.
- Valid junction-table records can be inserted.

### Invalid data
Verify that the database rejects:
- Invalid foreign keys
- Duplicate unique values
- NULL values in NOT NULL columns
- Values violating CHECK constraints
- Duplicate composite primary-key relationships

Also verify that the application can successfully connect to PostgreSQL.

---

## 16. Debugging

When an error occurs:

1. Read the complete error.
2. Identify the actual cause.
3. Explain the cause briefly.
4. Make the smallest appropriate fix.
5. Re-run the relevant test.

Do not make unrelated changes while fixing an error.

Do not hide errors or suppress exceptions merely to make the application run.

---

## 17. Assumptions

Do not silently make important assumptions.

If an implementation detail is ambiguous and could affect:
- Database structure
- Data integrity
- Application behavior
- API behavior
- Architecture

ask the user before proceeding.

For minor implementation details that do not affect the design, use reasonable conventions and clearly mention them.

---

## 18. Change Management

Before making a significant architectural or schema change:

- Explain what is being changed.
- Explain why it is necessary.
- Identify which part of `FINAL_SCHEMA.md` is affected.
- Ask for approval.

Do not silently modify the project's architecture.

---

## 19. Scope Control

Implement only what has been requested.

Do not automatically add:
- Authentication
- Authorization
- Caching
- Background workers
- Redis
- Celery
- Docker
- Cloud deployment
- Extra database tables
- Extra API endpoints
- Extra agents
- Extra features

unless they are explicitly part of the current task.

---

## 20. Priority Rules

When deciding how to implement something, follow this priority:

1. Explicit user instruction
2. `FINAL_SCHEMA.md`
3. `CODING_INSTRUCTIONS.md`
4. Existing project architecture
5. Reasonable implementation conventions

Never override an explicit user decision with a personal preference or generic "best practice."

---

## 21. Communication

Keep explanations concise and practical.

For each completed task, report:

### Implemented
- What was added/changed.

### Files Changed
- List the files.

### Validation
- What was tested.

### Issues / Assumptions
- Any important issue or assumption.

Do not provide unnecessary explanations of unrelated code.

---

## 22. First Task

Before implementing the application:

1. Read `FINAL_SCHEMA.md`.
2. Read `CODING_INSTRUCTIONS.md`.
3. Inspect the existing project structure.
4. Identify existing database-related files.
5. Do not modify anything yet.
6. Report your understanding of the project structure and proposed first implementation step.
7. Wait for user approval before making changes.