"""Tests for /api/companies and /api/jobs."""

from conftest import job_body, unique


# Anyone (even without logging in) can view companies and jobs.
def test_companies_and_jobs_are_public_to_read(client, job):
    assert client.get("/api/companies").status_code == 200
    assert client.get(f"/api/companies/{job['company_id']}").status_code == 200
    assert client.get("/api/jobs").status_code == 200
    assert client.get(f"/api/jobs/{job['job_id']}").status_code == 200


# Adding, replacing, editing or deleting a company needs a login (401 without).
def test_company_writes_require_login(client, job):
    company_id = job["company_id"]
    body = {"company_name": "X"}
    assert client.post("/api/companies", json={"company_id": unique("company"), **body}).status_code == 401
    assert client.put(f"/api/companies/{company_id}", json=body).status_code == 401
    assert client.patch(f"/api/companies/{company_id}", json=body).status_code == 401
    assert client.delete(f"/api/companies/{company_id}").status_code == 401


# Adding, replacing, editing or deleting a job needs a login (401 without).
def test_job_writes_require_login(client, job):
    job_id = job["job_id"]
    body = job_body(unique("job"), job["company_id"])
    assert client.post("/api/jobs", json=body).status_code == 401
    del body["job_id"]  # PUT takes everything except the id
    assert client.put(f"/api/jobs/{job_id}", json=body).status_code == 401
    assert client.patch(f"/api/jobs/{job_id}", json={"role": "X"}).status_code == 401
    assert client.delete(f"/api/jobs/{job_id}").status_code == 401


# A logged-in user can add, replace (PUT), edit (PATCH) and delete a company.
def test_company_crud_when_logged_in(client, rudra):
    _, headers = rudra
    company_id = unique("company")
    url = f"/api/companies/{company_id}"

    created = client.post("/api/companies", json={"company_id": company_id, "company_name": "Google"}, headers=headers)
    assert created.status_code == 201

    replaced = client.put(
        url,
        json={"company_name": "Google LLC", "company_site": "https://google.com", "company_description": "Search"},
        headers=headers,
    )
    assert replaced.status_code == 200
    assert replaced.json()["company_name"] == "Google LLC"

    # PATCH changes only the field we send; the name stays the same.
    edited = client.patch(url, json={"company_description": "Search and ads"}, headers=headers)
    assert edited.status_code == 200
    assert edited.json()["company_description"] == "Search and ads"
    assert edited.json()["company_name"] == "Google LLC"

    assert client.delete(url, headers=headers).status_code == 204


# A logged-in user can add, edit (PATCH), replace (PUT) and delete a job.
def test_job_crud_when_logged_in(client, rudra, job):
    _, headers = rudra
    job_id = unique("job")
    url = f"/api/jobs/{job_id}"
    body = job_body(job_id, job["company_id"])

    assert client.post("/api/jobs", json=body, headers=headers).status_code == 201

    edited = client.patch(url, json={"role": "Senior Backend Engineer"}, headers=headers)
    assert edited.status_code == 200
    assert edited.json()["role"] == "Senior Backend Engineer"

    del body["job_id"]
    replaced = client.put(url, json=body, headers=headers)
    assert replaced.status_code == 200
    assert replaced.json()["role"] == "Backend Engineer"

    assert client.delete(url, headers=headers).status_code == 204


# A company that still has jobs can't be deleted (409).
def test_company_with_jobs_cannot_be_deleted(client, rudra, job):
    _, headers = rudra
    assert client.delete(f"/api/companies/{job['company_id']}", headers=headers).status_code == 409


# Company and job lists come back one page at a time, with the totals alongside.
def test_companies_and_jobs_are_paginated(client, job):
    for url, key in [("/api/companies", "companies"), ("/api/jobs", "jobs")]:
        page = client.get(f"{url}?skip=0&limit=1").json()
        assert len(page[key]) == 1
        assert page["total"] >= 1
        assert page["skip"] == 0
        assert page["limit"] == 1
        assert page["has_more"] == (page["total"] > 1)

        # Without skip/limit you get the first page of the default size (10).
        assert client.get(url).json()["limit"] == 10


# skip can't be negative and limit must be between 1 and 100 (422 otherwise).
def test_bad_page_numbers_are_rejected(client):
    for query in ["skip=-1", "limit=0", "limit=101"]:
        assert client.get(f"/api/jobs?{query}").status_code == 422
