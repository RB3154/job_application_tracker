# Job Application Tracker

A personal job application tracker built with **FastAPI**.

This project is being developed as a practical backend project while learning and applying FastAPI concepts.

## 🚧 Current Status

**Initial Setup**

The first version contains the basic FastAPI application setup and a simple API endpoint.

## 🛠️ Tech Stack

* Python
* FastAPI
* Uvicorn
* Pydantic
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
└── uv.lock
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

The project will gradually evolve into a personal **Job Application Tracker / ATS**, with features for managing and tracking job applications throughout the job search process.

More functionality will be added incrementally as the project develops.
