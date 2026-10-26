"""Shared helpers (fixtures) for all test files. pytest loads this file automatically.

The tests use the real database from `.env`. Everything they create gets a random
name ending (e.g. `rudra_3f9a1c2b`) and is deleted again at the end.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import main


PASSWORD = "password123"


def unique(prefix: str) -> str:
    """Return a name with a random ending, e.g. unique("rudra") -> "rudra_3f9a1c2b"."""

    return f"{prefix}_{uuid4().hex[:8]}"


def make_user(client: TestClient, prefix: str) -> tuple[dict, dict]:
    """Sign up a new user and log them in.

    Returns (user, headers): `user` is the sign-up response, and `headers` holds the
    login token, so passing headers=headers is like being logged in with Authorize.
    """

    username = unique(prefix)
    email = f"{username}@test.com"
    response = client.post("/api/users", json={"username": username, "email": email, "password": PASSWORD})
    assert response.status_code == 201, response.text

    # The login form calls the field "username", but it takes the email.
    login = client.post("/api/users/token", data={"username": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return response.json(), headers


def job_body(job_id: str, company_id: str) -> dict:
    """The JSON needed to create a job."""

    return {
        "job_id": job_id,
        "role": "Backend Engineer",
        "JD": "Build APIs",
        "job_url": f"https://example.com/jobs/{job_id}",
        "job_posting_date": "2026-10-01",
        "company_id": company_id,
    }


@pytest.fixture(scope="session")
def client():
    """The "fake browser" that sends requests straight to the app.

    scope="session" means one client is shared by the whole test run, so the app
    starts once (like running uvicorn) and stops at the end.
    """

    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def rudra(client):
    """A logged-in test user. Their account is deleted after all tests finish."""

    user, headers = make_user(client, "rudra")
    yield user, headers
    client.delete("/api/users/me", headers=headers)


@pytest.fixture(scope="session")
def aman(client):
    """A second logged-in test user, used to check that users can't touch each other's data."""

    user, headers = make_user(client, "aman")
    yield user, headers
    client.delete("/api/users/me", headers=headers)


@pytest.fixture(scope="session")
def job(client, rudra):
    """A test company with one test job, for applications to use. Both are deleted at the end."""

    _, headers = rudra
    company_id = unique("company")
    job_id = unique("job")
    company = client.post("/api/companies", json={"company_id": company_id, "company_name": "Test Co"}, headers=headers)
    assert company.status_code == 201, company.text
    created_job = client.post("/api/jobs", json=job_body(job_id, company_id), headers=headers)
    assert created_job.status_code == 201, created_job.text

    yield {"company_id": company_id, "job_id": job_id}

    client.delete(f"/api/jobs/{job_id}", headers=headers)
    client.delete(f"/api/companies/{company_id}", headers=headers)
