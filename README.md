# Job Application Tracker

A personal **Job Application Tracker / ATS** built with **FastAPI** to help manage and track job applications throughout the job search process.

This project is being developed as a practical backend project while learning and applying FastAPI concepts.

## 🚧 Current Status

**Phase 2: FastAPI Fundamentals + Application Pages + Error Handling**

The project currently contains:

* FastAPI application setup
* Web-based dashboard UI
* Job application cards
* Individual job application pages
* Application status display
* Sidebar navigation
* Navigation bar
* Dark mode UI
* Static assets and HTML templates
* Jinja2 template rendering
* Dynamic URL path parameters
* JSON API endpoints
* Custom HTTP exception handling
* Custom request validation error handling
* Separate HTML and JSON error responses
* In-memory job application data

The current implementation uses Python data structures to store job applications. Database persistence and more advanced backend functionality will be added incrementally.

## 🛠️ Tech Stack

* Python
* FastAPI
* Uvicorn
* Pydantic
* Jinja2 Templates
* HTML
* CSS
* JavaScript
* uv
* Git & GitHub

## 📂 Project Structure

```text
job_application_tracker/
│
├── .gitignore
├── .python-version
├── README.md
├── main.py
├── pyproject.toml
├── uv.lock
│
├── static/
│   ├── css/
│   ├── js/
│   └── ...
│
└── templates/
    ├── error.html
    ├── home.html
    ├── layout.html
    └── post.html
```

## ⚙️ Current Backend Functionality

### Web Routes

The application currently provides HTML pages for:

```text
GET /
GET /posts
GET /posts/{post_id}
```

The `/posts/{post_id}` route uses a dynamic path parameter to display an individual job application.

### API Routes

The application also provides JSON API endpoints:

```text
GET /api/posts
GET /api/posts/{post_id}
```

These endpoints currently return the job application data stored in memory.

### Error Handling

The application includes custom exception handlers for:

* HTTP exceptions
* Request validation errors

The application distinguishes between API requests and normal webpage requests.

```text
Browser request
      ↓
HTML error page

API request
      ↓
JSON error response
```

For example, requesting a job application that does not exist produces a `404 Not Found` response.

Invalid path parameters are handled using FastAPI's request validation system and return a `422 Unprocessable Content` response.

## 📊 Current Data Model

Job applications are currently represented using Python dictionaries.

Each application contains information such as:

* ID
* Role
* Company
* Location
* Date applied
* Application status

Example:

```text
Job Application
├── id
├── role
├── company
├── location
├── date_applied
└── status
```

At this stage, the data is stored in memory rather than a database.

## 🚀 Running Locally

### Install dependencies

```bash
uv sync
```

### Start the development server

```bash
uv run uvicorn main:app --reload
```

The application will be available at:

```text
http://127.0.0.1:8000
```

### API Documentation

FastAPI automatically provides interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

## 🎯 Project Goal

The long-term goal is to evolve this project into a personal **Job Application Tracker / ATS** that can be genuinely used during the job search.

Planned functionality includes:

* Creating and managing job applications
* Tracking application status
* Storing company and role information
* Tracking application dates
* Updating application progress
* Searching and filtering applications
* Database persistence
* Authentication
* Dashboard statistics
* Additional ATS-style features

The project will be developed incrementally, with each stage introducing new backend and application-development concepts.

## 📌 Development Approach

The project is being built alongside learning **FastAPI**, with an emphasis on understanding the concepts rather than simply assembling a finished application.

The development process will progressively move from:

```text
FastAPI Fundamentals
        ↓
Frontend / Templates
        ↓
Dynamic Routes
        ↓
API Endpoints
        ↓
Error Handling
        ↓
Database Integration
        ↓
CRUD Operations
        ↓
Authentication
        ↓
Application Tracking
        ↓
Personal ATS
```

More functionality will be added as the project develops.

## 📚 Learning Reference

This project is being developed while following **Corey Schafer's FastAPI tutorial series** as a learning reference.

The project's current HTML templates, styling, and parts of the `main.py` structure are based on or adapted from the tutorial's examples. These files and patterns are being used for learning and understanding FastAPI concepts.

As development progresses, the project will increasingly incorporate my own implementation, architecture, features, and modifications to turn it into a personal Job Application Tracker / ATS.

**Credit:** Corey Schafer, for the FastAPI tutorial series used as a learning reference.
