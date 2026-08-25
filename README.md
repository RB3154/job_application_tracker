# Job Application Tracker

A personal **Job Application Tracker / ATS** built with **FastAPI** to help manage and track job applications throughout the job search process.

This project is being developed as a practical backend project while learning and applying FastAPI concepts.

## 🚧 Current Status

**Phase 1: Initial UI**

The project currently contains:

* FastAPI application setup
* Web-based dashboard UI
* Job application cards
* Application status display
* Sidebar navigation
* Navigation bar
* Dark mode UI
* Static assets and HTML templates
* Responsive frontend structure

The application is currently focused on establishing the core UI and project structure. Backend functionality and database-driven features will be added incrementally.

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
    ├── ...
    └── ...
```

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
