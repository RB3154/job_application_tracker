from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.conftest import create_application, create_company, create_job, create_lookup, job_payload


pytestmark = pytest.mark.anyio


async def attach(client: AsyncClient, headers: dict, job_id: str, **details) -> None:
    response = await client.put(f"/api/jobs/{job_id}/details", json=details, headers=headers)
    assert response.status_code == 200, response.text


def job_ids(response) -> list[str]:
    return [job["job_id"] for job in response.json()["jobs"]]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/jobs"),
        ("POST", "/api/jobs"),
        ("GET", "/api/jobs/some-job"),
        ("PUT", "/api/jobs/some-job"),
        ("PATCH", "/api/jobs/some-job"),
        ("DELETE", "/api/jobs/some-job"),
        ("GET", "/api/jobs/some-job/details"),
        ("PUT", "/api/jobs/some-job/details"),
    ],
)
async def test_job_routes_need_login(client: AsyncClient, method: str, path: str):
    response = await client.request(method, path)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


async def test_create_job_success(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, name="Acme")

    response = await client.post(
        "/api/jobs",
        json=job_payload(
            company["company_id"],
            JD="Build APIs",
            application_deadline="2026-02-15",
            exp_min=1,
            exp_max=3.5,
            exp_text="1-3 years",
            salary_min=500000,
            salary_max=900000,
            salary_text="5-9 LPA",
            salary_currency="INR",
            salary_period="year",
        ),
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["job_id"] == "acme-backend-engineer"
    assert data["role"] == "Backend Engineer"
    assert data["JD"] == "Build APIs"
    assert data["job_posting_date"] == "2026-01-15"
    assert data["application_deadline"] == "2026-02-15"
    assert Decimal(data["exp_max"]) == Decimal("3.5")
    assert Decimal(data["salary_max"]) == Decimal("900000")
    assert data["salary_currency"] == "INR"
    assert data["company_id"] == "acme"


async def test_create_job_description_is_optional(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)

    assert job["JD"] is None


async def test_create_job_keeps_url_exactly_as_typed(client: AsyncClient, headers: dict):
    job = await create_job(client, headers, job_url="https://Example.com/job?id=1")

    assert job["job_url"] == "https://Example.com/job?id=1"


async def test_create_job_same_role_gets_new_id(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, name="Acme")

    first = await create_job(client, headers, company["company_id"], job_url="https://example.com/1")
    second = await create_job(client, headers, company["company_id"], job_url="https://example.com/2")

    assert first["job_id"] == "acme-backend-engineer"
    assert second["job_id"] == "acme-backend-engineer-2"


async def test_create_job_duplicate_url(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    await create_job(client, headers, company["company_id"])

    response = await client.post("/api/jobs", json=job_payload(company["company_id"], role="Other"), headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "You already saved a job with this link"


async def test_create_job_same_url_for_different_users(client: AsyncClient, headers: dict, other_headers: dict):
    first = await create_job(client, headers)
    second = await create_job(client, other_headers)

    assert first["job_url"] == second["job_url"]
    assert first["job_id"] != second["job_id"]


async def test_create_job_unknown_company(client: AsyncClient, headers: dict):
    response = await client.post("/api/jobs", json=job_payload("nope"), headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"


async def test_create_job_at_someone_elses_company(client: AsyncClient, headers: dict, other_headers: dict):
    their_company = await create_company(client, other_headers)

    response = await client.post("/api/jobs", json=job_payload(their_company["company_id"]), headers=headers)

    assert response.status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"role": ""},
        {"role": "x" * 256},
        {"job_url": ""},
        {"job_url": "not a url"},
        {"job_url": "javascript:alert(1)"},
        {"job_posting_date": "not a date"},
        {"application_deadline": "2026-01-14"},
        {"exp_min": -1},
        {"exp_max": -1},
        {"exp_min": 5, "exp_max": 2},
        {"salary_min": -1},
        {"salary_max": -1},
        {"salary_min": 100, "salary_max": 50},
        {"salary_currency": "RUPEES"},
        {"salary_period": "x" * 21},
    ],
)
async def test_create_job_invalid_values(client: AsyncClient, headers: dict, changes: dict):
    company = await create_company(client, headers)

    response = await client.post("/api/jobs", json=job_payload(company["company_id"], **changes), headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["role", "job_url", "job_posting_date", "company_id"])
async def test_create_job_missing_required_field(client: AsyncClient, headers: dict, field: str):
    company = await create_company(client, headers)
    body = job_payload(company["company_id"])
    del body[field]

    response = await client.post("/api/jobs", json=body, headers=headers)

    assert response.status_code == 422
    assert field in response.text


async def test_get_jobs_empty(client: AsyncClient, headers: dict):
    response = await client.get("/api/jobs", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["jobs"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


async def test_get_jobs_with_pagination(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    for i in range(5):
        await create_job(client, headers, company["company_id"], job_url=f"https://example.com/{i}")

    data = (await client.get("/api/jobs", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["jobs"]) == 5
    assert data["has_more"] is False

    data = (await client.get("/api/jobs?limit=2", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["jobs"]) == 2
    assert data["has_more"] is True

    data = (await client.get("/api/jobs?skip=2&limit=2", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["jobs"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2


@pytest.mark.parametrize("query", ["skip=-1", "limit=0", "limit=101", f"q={'x' * 101}", "location_id=abc"])
async def test_get_jobs_invalid_query(client: AsyncClient, headers: dict, query: str):
    response = await client.get(f"/api/jobs?{query}", headers=headers)

    assert response.status_code == 422


async def test_get_jobs_newest_posting_first(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    dates = ["2026-01-01", "2026-03-01", "2026-02-01"]
    for i, posted in enumerate(dates):
        await create_job(
            client, headers, company["company_id"], job_url=f"https://example.com/{i}", job_posting_date=posted
        )

    data = (await client.get("/api/jobs", headers=headers)).json()

    assert [job["job_posting_date"] for job in data["jobs"]] == ["2026-03-01", "2026-02-01", "2026-01-01"]


async def test_get_jobs_only_shows_my_own(client: AsyncClient, headers: dict, other_headers: dict):
    mine = await create_job(client, headers)
    await create_job(client, other_headers)

    response = await client.get("/api/jobs", headers=headers)

    assert job_ids(response) == [mine["job_id"]]
    assert response.json()["total"] == 1


@pytest.mark.parametrize(
    ("q", "matches"),
    [
        ("backend", {"backend"}),
        ("FRONTEND", {"frontend"}),
        ("globex", {"frontend"}),
        ("engineer", {"backend", "frontend"}),
        ("%", set()),
        ("nothing-like-this", set()),
        ("  backend  ", {"backend"}),
    ],
)
async def test_get_jobs_search(client: AsyncClient, headers: dict, q: str, matches: set[str]):
    acme = await create_company(client, headers, name="Acme")
    globex = await create_company(client, headers, name="Globex")
    backend = await create_job(
        client, headers, acme["company_id"], role="Backend Engineer", job_url="https://example.com/1"
    )
    frontend = await create_job(
        client, headers, globex["company_id"], role="Frontend Engineer", job_url="https://example.com/2"
    )
    ids = {"backend": backend["job_id"], "frontend": frontend["job_id"]}

    response = await client.get("/api/jobs", params={"q": q}, headers=headers)

    assert response.status_code == 200
    assert set(job_ids(response)) == {ids[name] for name in matches}


async def test_get_jobs_filter_by_company(client: AsyncClient, headers: dict):
    acme = await create_company(client, headers, name="Acme")
    globex = await create_company(client, headers, name="Globex")
    job = await create_job(client, headers, acme["company_id"], job_url="https://example.com/1")
    await create_job(client, headers, globex["company_id"], job_url="https://example.com/2")

    response = await client.get("/api/jobs", params={"company_id": "acme"}, headers=headers)

    assert job_ids(response) == [job["job_id"]]


@pytest.mark.parametrize(
    ("list_path", "param", "details_key"),
    [
        ("/api/locations", "location_id", "location_ids"),
        ("/api/work-modes", "work_mode_id", "work_mode_ids"),
        ("/api/skills", "skill_id", "skills"),
    ],
)
async def test_get_jobs_filter_by_lookup(
    client: AsyncClient, headers: dict, list_path: str, param: str, details_key: str
):
    company = await create_company(client, headers)
    wanted = await create_job(client, headers, company["company_id"], job_url="https://example.com/1")
    await create_job(client, headers, company["company_id"], job_url="https://example.com/2")
    entry = await create_lookup(client, headers, list_path, "Some entry")
    value = [{"skill_id": entry["id"]}] if details_key == "skills" else [entry["id"]]
    await attach(client, headers, wanted["job_id"], **{details_key: value})

    response = await client.get("/api/jobs", params={param: entry["id"]}, headers=headers)

    assert job_ids(response) == [wanted["job_id"]]
    assert response.json()["total"] == 1


async def test_get_jobs_empty_filters_mean_no_filter(client: AsyncClient, headers: dict):
    await create_job(client, headers)

    response = await client.get("/api/jobs?q=&company_id=&location_id=&skill_id=&work_mode_id=", headers=headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_get_jobs_open_only(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    today = date.today()
    long_ago = (today - timedelta(days=30)).isoformat()

    async def add(number: int, deadline: date | None) -> str:
        job = await create_job(
            client,
            headers,
            company["company_id"],
            job_url=f"https://example.com/{number}",
            job_posting_date=long_ago,
            application_deadline=deadline.isoformat() if deadline else None,
        )
        return job["job_id"]

    no_deadline = await add(1, None)
    due_today = await add(2, today)
    due_later = await add(3, today + timedelta(days=1))
    expired = await add(4, today - timedelta(days=1))

    open_jobs = await client.get("/api/jobs?open_only=true", headers=headers)
    all_jobs = await client.get("/api/jobs", headers=headers)

    assert set(job_ids(open_jobs)) == {no_deadline, due_today, due_later}
    assert expired in job_ids(all_jobs)


async def test_get_job(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)

    response = await client.get(f"/api/jobs/{job['job_id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == job


async def test_get_job_not_found(client: AsyncClient, headers: dict):
    response = await client.get("/api/jobs/nope", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


async def test_update_job_only_changes_what_was_sent(client: AsyncClient, headers: dict):
    job = await create_job(client, headers, JD="Original")

    response = await client.patch(f"/api/jobs/{job['job_id']}", json={"role": "Senior Engineer"}, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "Senior Engineer"
    assert data["JD"] == "Original"
    assert data["job_id"] == job["job_id"]


async def test_update_job_can_clear_optional_field(client: AsyncClient, headers: dict):
    job = await create_job(client, headers, JD="Original")

    response = await client.patch(f"/api/jobs/{job['job_id']}", json={"JD": None}, headers=headers)

    assert response.status_code == 200
    assert response.json()["JD"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"role": None},
        {"role": ""},
        {"job_url": None},
        {"job_url": "not a url"},
        {"job_posting_date": None},
        {"company_id": None},
        {"exp_min": -1},
    ],
)
async def test_update_job_invalid_values(client: AsyncClient, headers: dict, body: dict):
    job = await create_job(client, headers)

    response = await client.patch(f"/api/jobs/{job['job_id']}", json=body, headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"exp_max": 1},
        {"salary_max": 50},
        {"application_deadline": "2026-01-01"},
        {"job_posting_date": "2026-12-31"},
    ],
)
async def test_update_job_ranges_checked_against_saved_values(client: AsyncClient, headers: dict, body: dict):
    job = await create_job(client, headers, exp_min=2, salary_min=100, application_deadline="2026-02-01")

    response = await client.patch(f"/api/jobs/{job['job_id']}", json=body, headers=headers)

    assert response.status_code == 422


async def test_update_job_url_taken_by_my_other_job(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    await create_job(client, headers, company["company_id"], job_url="https://example.com/1")
    second = await create_job(client, headers, company["company_id"], job_url="https://example.com/2")

    response = await client.patch(
        f"/api/jobs/{second['job_id']}", json={"job_url": "https://example.com/1"}, headers=headers
    )

    assert response.status_code == 409


async def test_update_job_can_keep_own_url(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)

    response = await client.patch(f"/api/jobs/{job['job_id']}", json={"job_url": job["job_url"]}, headers=headers)

    assert response.status_code == 200


async def test_update_job_move_to_my_other_company(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)
    other_company = await create_company(client, headers, name="Globex")

    response = await client.patch(
        f"/api/jobs/{job['job_id']}", json={"company_id": other_company["company_id"]}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["company_id"] == "globex"


async def test_update_job_cant_move_to_someone_elses_company(client: AsyncClient, headers: dict, other_headers: dict):
    job = await create_job(client, headers)
    their_company = await create_company(client, other_headers, name="Globex")

    response = await client.patch(
        f"/api/jobs/{job['job_id']}", json={"company_id": their_company["company_id"]}, headers=headers
    )

    assert response.status_code == 404


async def test_replace_job_clears_fields_left_out(client: AsyncClient, headers: dict):
    job = await create_job(client, headers, JD="Original", exp_text="2 years")

    response = await client.put(
        f"/api/jobs/{job['job_id']}", json=job_payload(job["company_id"], role="New role"), headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "New role"
    assert data["JD"] is None
    assert data["exp_text"] is None


async def test_replace_job_needs_required_fields(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)

    response = await client.put(f"/api/jobs/{job['job_id']}", json={"role": "Only a role"}, headers=headers)

    assert response.status_code == 422


async def test_delete_job(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)

    response = await client.delete(f"/api/jobs/{job['job_id']}", headers=headers)

    assert response.status_code == 204
    assert (await client.get(f"/api/jobs/{job['job_id']}", headers=headers)).status_code == 404


async def test_delete_job_with_application_is_refused(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)
    await create_application(client, headers, job["job_id"])

    response = await client.delete(f"/api/jobs/{job['job_id']}", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Job has applications and cannot be deleted"


async def test_delete_job_removes_its_details(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)
    skill = await create_lookup(client, headers, "/api/skills", "Python")
    await attach(client, headers, job["job_id"], skills=[{"skill_id": skill["id"]}])

    response = await client.delete(f"/api/jobs/{job['job_id']}", headers=headers)
    assert response.status_code == 204

    response = await client.delete(f"/api/skills/{skill['id']}", headers=headers)
    assert response.status_code == 204


async def test_job_details_start_empty(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)

    response = await client.get(f"/api/jobs/{job['job_id']}/details", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"locations": [], "work_modes": [], "sources": [], "skills": [], "education": []}


async def test_replace_job_details(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)
    pune = await create_lookup(client, headers, "/api/locations", "Pune")
    delhi = await create_lookup(client, headers, "/api/locations", "Delhi")
    remote = await create_lookup(client, headers, "/api/work-modes", "Remote")
    linkedin = await create_lookup(client, headers, "/api/sources", "LinkedIn")
    python = await create_lookup(client, headers, "/api/skills", "Python")
    docker = await create_lookup(client, headers, "/api/skills", "Docker")
    btech = await create_lookup(client, headers, "/api/education", "B.Tech")

    response = await client.put(
        f"/api/jobs/{job['job_id']}/details",
        json={
            "location_ids": [pune["id"], delhi["id"]],
            "work_mode_ids": [remote["id"]],
            "source_ids": [linkedin["id"]],
            "skills": [{"skill_id": python["id"]}, {"skill_id": docker["id"], "skill_type": "preferred"}],
            "education": [{"education_id": btech["id"], "note": "CS preferred"}],
        },
        headers=headers,
    )

    assert response.status_code == 200
    expected = {
        "locations": [delhi, pune],
        "work_modes": [remote],
        "sources": [linkedin],
        "skills": [
            {"id": docker["id"], "name": "Docker", "skill_type": "preferred"},
            {"id": python["id"], "name": "Python", "skill_type": "required"},
        ],
        "education": [{"id": btech["id"], "name": "B.Tech", "note": "CS preferred"}],
    }
    assert response.json() == expected
    assert (await client.get(f"/api/jobs/{job['job_id']}/details", headers=headers)).json() == expected


async def test_replace_job_details_removes_what_was_left_out(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)
    delhi = await create_lookup(client, headers, "/api/locations", "Delhi")
    python = await create_lookup(client, headers, "/api/skills", "Python")
    await attach(client, headers, job["job_id"], location_ids=[delhi["id"]], skills=[{"skill_id": python["id"]}])

    response = await client.put(
        f"/api/jobs/{job['job_id']}/details", json={"location_ids": [delhi["id"]]}, headers=headers
    )

    assert response.json()["locations"] == [delhi]
    assert response.json()["skills"] == []


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"location_ids": [999999]}, "Location not found: 999999"),
        ({"work_mode_ids": [999999]}, "Work mode not found: 999999"),
        ({"source_ids": [999999]}, "Source not found: 999999"),
        ({"skills": [{"skill_id": 999999}]}, "Skill not found: 999999"),
        ({"education": [{"education_id": 999999}]}, "Education requirement not found: 999999"),
    ],
)
async def test_replace_job_details_unknown_id(client: AsyncClient, headers: dict, body: dict, detail: str):
    job = await create_job(client, headers)

    response = await client.put(f"/api/jobs/{job['job_id']}/details", json=body, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == detail


async def test_replace_job_details_failure_keeps_old_details(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)
    delhi = await create_lookup(client, headers, "/api/locations", "Delhi")
    await attach(client, headers, job["job_id"], location_ids=[delhi["id"]])

    await client.put(f"/api/jobs/{job['job_id']}/details", json={"location_ids": [999999]}, headers=headers)

    details = (await client.get(f"/api/jobs/{job['job_id']}/details", headers=headers)).json()
    assert details["locations"] == [delhi]


@pytest.mark.parametrize(
    "body",
    [
        {"location_ids": [1, 1]},
        {"work_mode_ids": [1, 1]},
        {"source_ids": [1, 1]},
        {"skills": [{"skill_id": 1}, {"skill_id": 1, "skill_type": "preferred"}]},
        {"education": [{"education_id": 1}, {"education_id": 1}]},
        {"skills": [{"skill_id": 1, "skill_type": "nice to have"}]},
    ],
)
async def test_replace_job_details_invalid(client: AsyncClient, headers: dict, body: dict):
    job = await create_job(client, headers)

    response = await client.put(f"/api/jobs/{job['job_id']}/details", json=body, headers=headers)

    assert response.status_code == 422


async def test_replace_job_details_with_someone_elses_entry(client: AsyncClient, headers: dict, other_headers: dict):
    job = await create_job(client, headers)
    their_skill = await create_lookup(client, other_headers, "/api/skills", "Python")

    response = await client.put(
        f"/api/jobs/{job['job_id']}/details", json={"skills": [{"skill_id": their_skill["id"]}]}, headers=headers
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("PATCH", "", {"role": "Hacked"}),
        ("DELETE", "", None),
        ("GET", "/details", None),
        ("PUT", "/details", {}),
    ],
)
async def test_other_users_job_is_404(
    client: AsyncClient, headers: dict, other_headers: dict, method: str, suffix: str, body: dict | None
):
    job = await create_job(client, headers)
    path = f"/api/jobs/{job['job_id']}"

    response = await client.request(method, path + suffix, json=body, headers=other_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"
    assert (await client.get(path, headers=headers)).json()["role"] == job["role"]


async def test_replace_other_users_job_is_404(client: AsyncClient, headers: dict, other_headers: dict):
    job = await create_job(client, headers)
    their_company = await create_company(client, other_headers, name="Globex")

    response = await client.put(
        f"/api/jobs/{job['job_id']}", json=job_payload(their_company["company_id"]), headers=other_headers
    )

    assert response.status_code == 404
