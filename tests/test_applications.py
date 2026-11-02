from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient

from tests.conftest import create_application, create_company, create_job


pytestmark = pytest.mark.anyio


def quick_payload(**fields) -> dict:
    return {
        "company_name": "Acme",
        "role": "Backend Engineer",
        "job_url": "https://careers.example.com/1",
        **fields,
    }


async def quick_create(client: AsyncClient, headers: dict, **fields) -> dict:
    response = await client.post("/api/applications/quick", json=quick_payload(**fields), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def get_history(client: AsyncClient, headers: dict, application_id: int) -> list[tuple]:
    response = await client.get(f"/api/applications/{application_id}/history", headers=headers)
    assert response.status_code == 200
    return [(entry["from_status"], entry["to_status"]) for entry in response.json()]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/applications"),
        ("POST", "/api/applications"),
        ("POST", "/api/applications/quick"),
        ("GET", "/api/applications/1"),
        ("GET", "/api/applications/1/history"),
        ("PUT", "/api/applications/1"),
        ("PATCH", "/api/applications/1"),
        ("DELETE", "/api/applications/1"),
    ],
)
async def test_application_routes_need_login(client: AsyncClient, method: str, path: str):
    response = await client.request(method, path)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


async def test_create_application_uses_defaults(client: AsyncClient, headers: dict):
    job = await create_job(client, headers)
    me = (await client.get("/api/users/me", headers=headers)).json()

    response = await client.post("/api/applications", json={"job_id": job["job_id"]}, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["job_id"] == job["job_id"]
    assert data["user_id"] == me["id"]
    assert data["current_status"] == "Applied"
    assert data["interview_rounds"] == 0
    assert data["notes"] is None
    assert abs(date.fromisoformat(data["date_applied"]) - date.today()) <= timedelta(days=1)


async def test_create_application_with_all_fields(client: AsyncClient, headers: dict):
    application = await create_application(
        client,
        headers,
        date_applied="2026-03-01",
        current_status="Interview",
        interview_rounds=2,
        notes="Call on Monday",
    )

    assert application["date_applied"] == "2026-03-01"
    assert application["current_status"] == "Interview"
    assert application["interview_rounds"] == 2
    assert application["notes"] == "Call on Monday"


async def test_create_application_null_means_use_the_default(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, date_applied=None, current_status=None)

    assert application["current_status"] == "Applied"
    assert application["date_applied"] is not None


@pytest.mark.parametrize(
    "status", ["Wishlist", "Applied", "Screening", "Interview", "Rejected", "Offer", "Accepted", "Withdrawn"]
)
async def test_create_application_every_status(client: AsyncClient, headers: dict, status: str):
    application = await create_application(client, headers, current_status=status)

    assert application["current_status"] == status


@pytest.mark.parametrize(
    "changes",
    [
        {"current_status": "Hired"},
        {"interview_rounds": -1},
        {"notes": "x" * 5001},
        {"date_applied": "not a date"},
    ],
)
async def test_create_application_invalid_values(client: AsyncClient, headers: dict, changes: dict):
    job = await create_job(client, headers)

    response = await client.post("/api/applications", json={"job_id": job["job_id"], **changes}, headers=headers)

    assert response.status_code == 422


async def test_create_application_missing_job_id(client: AsyncClient, headers: dict):
    response = await client.post("/api/applications", json={}, headers=headers)

    assert response.status_code == 422
    assert "job_id" in response.text


async def test_create_application_unknown_job(client: AsyncClient, headers: dict):
    response = await client.post("/api/applications", json={"job_id": "nope"}, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


async def test_create_application_for_someone_elses_job(client: AsyncClient, headers: dict, other_headers: dict):
    their_job = await create_job(client, other_headers)

    response = await client.post("/api/applications", json={"job_id": their_job["job_id"]}, headers=headers)

    assert response.status_code == 404


async def test_create_application_twice_for_same_job(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)

    response = await client.post("/api/applications", json={"job_id": application["job_id"]}, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "This user has already applied to this job"


async def test_get_applications_empty(client: AsyncClient, headers: dict):
    response = await client.get("/api/applications", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["applications"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


async def test_get_applications_with_pagination(client: AsyncClient, headers: dict):
    for i in range(5):
        await quick_create(client, headers, job_url=f"https://example.com/{i}")

    data = (await client.get("/api/applications", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["applications"]) == 5
    assert data["has_more"] is False

    data = (await client.get("/api/applications?limit=2", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["applications"]) == 2
    assert data["has_more"] is True

    data = (await client.get("/api/applications?skip=2&limit=2", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["applications"]) == 2
    assert data["skip"] == 2
    assert data["limit"] == 2


@pytest.mark.parametrize("query", ["skip=-1", "limit=0", "limit=101", "status=Hired"])
async def test_get_applications_invalid_query(client: AsyncClient, headers: dict, query: str):
    response = await client.get(f"/api/applications?{query}", headers=headers)

    assert response.status_code == 422


async def test_get_applications_most_recent_first(client: AsyncClient, headers: dict):
    for i, applied in enumerate(["2026-01-01", "2026-03-01", "2026-02-01"]):
        await quick_create(client, headers, job_url=f"https://example.com/{i}", date_applied=applied)

    data = (await client.get("/api/applications", headers=headers)).json()

    assert [item["date_applied"] for item in data["applications"]] == ["2026-03-01", "2026-02-01", "2026-01-01"]


async def test_get_applications_filter_by_status(client: AsyncClient, headers: dict):
    await quick_create(client, headers, job_url="https://example.com/1", current_status="Applied")
    wanted = await quick_create(client, headers, job_url="https://example.com/2", current_status="Offer")

    data = (await client.get("/api/applications?status=Offer", headers=headers)).json()

    assert data["total"] == 1
    assert data["applications"][0]["application_id"] == wanted["application_id"]


async def test_get_applications_includes_last_status_change(client: AsyncClient, headers: dict):
    await create_application(client, headers)

    data = (await client.get("/api/applications", headers=headers)).json()

    assert data["applications"][0]["last_status_change"] is not None


async def test_get_applications_only_shows_my_own(client: AsyncClient, headers: dict, other_headers: dict):
    mine = await create_application(client, headers)
    await create_application(client, other_headers)

    data = (await client.get("/api/applications", headers=headers)).json()

    assert data["total"] == 1
    assert data["applications"][0]["application_id"] == mine["application_id"]


async def test_get_application(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)

    response = await client.get(f"/api/applications/{application['application_id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == application


async def test_get_application_not_found(client: AsyncClient, headers: dict):
    response = await client.get("/api/applications/999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


async def test_get_application_id_must_be_a_number(client: AsyncClient, headers: dict):
    response = await client.get("/api/applications/abc", headers=headers)

    assert response.status_code == 422


async def test_update_application_only_changes_what_was_sent(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, notes="Original", date_applied="2026-03-01")

    response = await client.patch(
        f"/api/applications/{application['application_id']}", json={"interview_rounds": 3}, headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["interview_rounds"] == 3
    assert data["notes"] == "Original"
    assert data["date_applied"] == "2026-03-01"


async def test_update_application_can_clear_notes(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, notes="Original")

    response = await client.patch(
        f"/api/applications/{application['application_id']}", json={"notes": None}, headers=headers
    )

    assert response.json()["notes"] is None


@pytest.mark.parametrize(
    "body",
    [
        {"job_id": None},
        {"date_applied": None},
        {"interview_rounds": None},
        {"interview_rounds": -1},
        {"current_status": "Hired"},
        {"notes": "x" * 5001},
    ],
)
async def test_update_application_invalid_values(client: AsyncClient, headers: dict, body: dict):
    application = await create_application(client, headers)

    response = await client.patch(f"/api/applications/{application['application_id']}", json=body, headers=headers)

    assert response.status_code == 422


async def test_update_application_move_to_my_other_job(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)
    other_job = await create_job(client, headers, job_url="https://example.com/2")

    response = await client.patch(
        f"/api/applications/{application['application_id']}", json={"job_id": other_job["job_id"]}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == other_job["job_id"]


async def test_update_application_job_already_tracked(client: AsyncClient, headers: dict):
    first = await quick_create(client, headers, job_url="https://example.com/1")
    second = await quick_create(client, headers, job_url="https://example.com/2")

    response = await client.patch(
        f"/api/applications/{second['application_id']}", json={"job_id": first["job_id"]}, headers=headers
    )

    assert response.status_code == 409


async def test_update_application_cant_move_to_someone_elses_job(
    client: AsyncClient, headers: dict, other_headers: dict
):
    application = await create_application(client, headers)
    their_job = await create_job(client, other_headers)

    response = await client.patch(
        f"/api/applications/{application['application_id']}", json={"job_id": their_job["job_id"]}, headers=headers
    )

    assert response.status_code == 404


async def test_replace_application_resets_fields_left_out(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, notes="Original", interview_rounds=2)

    response = await client.put(
        f"/api/applications/{application['application_id']}",
        json={"job_id": application["job_id"], "date_applied": "2026-03-01"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["date_applied"] == "2026-03-01"
    assert data["notes"] is None
    assert data["interview_rounds"] == 0


async def test_replace_application_left_out_status_goes_back_to_applied(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, current_status="Interview")

    response = await client.put(
        f"/api/applications/{application['application_id']}",
        json={"job_id": application["job_id"], "date_applied": "2026-03-01"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["current_status"] == "Applied"


async def test_update_application_rejects_empty_status(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)

    response = await client.patch(
        f"/api/applications/{application['application_id']}", json={"current_status": None}, headers=headers
    )

    assert response.status_code == 422


async def test_replace_application_needs_required_fields(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)

    response = await client.put(
        f"/api/applications/{application['application_id']}", json={"job_id": application["job_id"]}, headers=headers
    )

    assert response.status_code == 422
    assert "date_applied" in response.text


async def test_history_starts_with_creation(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, current_status="Screening")

    assert await get_history(client, headers, application["application_id"]) == [(None, "Screening")]


async def test_history_without_a_status_records_the_default(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)

    assert await get_history(client, headers, application["application_id"]) == [(None, "Applied")]


async def test_history_records_each_status_change_in_order(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)
    path = f"/api/applications/{application['application_id']}"

    await client.patch(path, json={"current_status": "Interview"}, headers=headers)
    await client.put(
        path,
        json={"job_id": application["job_id"], "date_applied": "2026-03-01", "current_status": "Offer"},
        headers=headers,
    )

    assert await get_history(client, headers, application["application_id"]) == [
        (None, "Applied"),
        ("Applied", "Interview"),
        ("Interview", "Offer"),
    ]


async def test_history_ignores_changes_that_keep_the_status(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)
    path = f"/api/applications/{application['application_id']}"

    await client.patch(path, json={"current_status": "Applied"}, headers=headers)
    await client.patch(path, json={"notes": "No status here"}, headers=headers)

    assert await get_history(client, headers, application["application_id"]) == [(None, "Applied")]


async def test_history_entries_have_a_time(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)

    response = await client.get(f"/api/applications/{application['application_id']}/history", headers=headers)

    assert response.json()[0]["changed_at"] is not None


async def test_history_not_found(client: AsyncClient, headers: dict):
    response = await client.get("/api/applications/999999/history", headers=headers)

    assert response.status_code == 404


async def test_leaving_wishlist_sets_date_to_today(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, current_status="Wishlist", date_applied="2026-01-01")

    response = await client.patch(
        f"/api/applications/{application['application_id']}", json={"current_status": "Applied"}, headers=headers
    )

    assert response.json()["date_applied"] == date.today().isoformat()


async def test_leaving_wishlist_keeps_a_date_that_was_sent(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, current_status="Wishlist", date_applied="2026-01-01")

    response = await client.patch(
        f"/api/applications/{application['application_id']}",
        json={"current_status": "Applied", "date_applied": "2026-02-02"},
        headers=headers,
    )

    assert response.json()["date_applied"] == "2026-02-02"


async def test_staying_on_wishlist_keeps_the_date(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, current_status="Wishlist", date_applied="2026-01-01")

    response = await client.patch(
        f"/api/applications/{application['application_id']}", json={"notes": "Still thinking"}, headers=headers
    )

    assert response.json()["date_applied"] == "2026-01-01"


async def test_other_status_changes_keep_the_date(client: AsyncClient, headers: dict):
    application = await create_application(client, headers, current_status="Applied", date_applied="2026-01-01")

    response = await client.patch(
        f"/api/applications/{application['application_id']}", json={"current_status": "Interview"}, headers=headers
    )

    assert response.json()["date_applied"] == "2026-01-01"


async def test_delete_application(client: AsyncClient, headers: dict):
    application = await create_application(client, headers)
    path = f"/api/applications/{application['application_id']}"

    response = await client.delete(path, headers=headers)

    assert response.status_code == 204
    assert (await client.get(path, headers=headers)).status_code == 404
    assert (await client.delete(f"/api/jobs/{application['job_id']}", headers=headers)).status_code == 204


async def test_quick_create_makes_company_job_and_application(client: AsyncClient, headers: dict):
    response = await client.post("/api/applications/quick", json=quick_payload(notes="Referred"), headers=headers)

    assert response.status_code == 201
    application = response.json()
    assert application["current_status"] == "Applied"
    assert application["notes"] == "Referred"
    assert application["job_id"] == "acme-backend-engineer"

    job = (await client.get(f"/api/jobs/{application['job_id']}", headers=headers)).json()
    assert job["role"] == "Backend Engineer"
    assert job["job_url"] == "https://careers.example.com/1"
    assert job["company_id"] == "acme"
    assert job["job_posting_date"] == date.today().isoformat()

    company = (await client.get("/api/companies/acme", headers=headers)).json()
    assert company["company_name"] == "Acme"

    assert await get_history(client, headers, application["application_id"]) == [(None, "Applied")]


async def test_quick_create_saves_optional_details(client: AsyncClient, headers: dict):
    application = await quick_create(
        client,
        headers,
        job_posting_date="2026-01-01",
        application_deadline="2026-02-01",
        exp_min=1,
        exp_max=3,
        salary_min=100,
        salary_max=200,
        salary_currency="INR",
        JD="Build APIs",
        company_site="https://acme.example.com",
        company_description="Makes things",
        current_status="Wishlist",
        date_applied="2026-01-05",
        interview_rounds=1,
    )

    assert application["current_status"] == "Wishlist"
    assert application["date_applied"] == "2026-01-05"
    assert application["interview_rounds"] == 1

    job = (await client.get(f"/api/jobs/{application['job_id']}", headers=headers)).json()
    assert job["job_posting_date"] == "2026-01-01"
    assert job["application_deadline"] == "2026-02-01"
    assert Decimal(job["exp_max"]) == 3
    assert Decimal(job["salary_max"]) == 200
    assert job["salary_currency"] == "INR"
    assert job["JD"] == "Build APIs"

    company = (await client.get(f"/api/companies/{job['company_id']}", headers=headers)).json()
    assert company["company_site"] == "https://acme.example.com"
    assert company["company_description"] == "Makes things"


async def test_quick_create_trims_spaces(client: AsyncClient, headers: dict):
    application = await quick_create(client, headers, company_name="  Acme  ", role="  Engineer  ")

    job = (await client.get(f"/api/jobs/{application['job_id']}", headers=headers)).json()
    company = (await client.get(f"/api/companies/{job['company_id']}", headers=headers)).json()
    assert job["role"] == "Engineer"
    assert company["company_name"] == "Acme"


async def test_quick_create_reuses_company_ignoring_case(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, name="Acme")

    application = await quick_create(client, headers, company_name="ACME")

    job = (await client.get(f"/api/jobs/{application['job_id']}", headers=headers)).json()
    assert job["company_id"] == company["company_id"]
    assert (await client.get("/api/companies", headers=headers)).json()["total"] == 1


async def test_quick_create_never_reuses_someone_elses_company(client: AsyncClient, headers: dict, other_headers: dict):
    their_company = await create_company(client, other_headers, name="Acme", company_description="Theirs")

    application = await quick_create(client, headers, company_name="Acme", company_description="Mine")

    job = (await client.get(f"/api/jobs/{application['job_id']}", headers=headers)).json()
    assert job["company_id"] != their_company["company_id"]
    theirs = await client.get(f"/api/companies/{their_company['company_id']}", headers=other_headers)
    assert theirs.json()["company_description"] == "Theirs"


async def test_quick_create_reuses_job_with_same_link(client: AsyncClient, headers: dict):
    job = await create_job(client, headers, job_url="https://example.com/1", role="Original role")

    application = await quick_create(
        client, headers, job_url="https://example.com/1", company_name="Different", role="Different role"
    )

    assert application["job_id"] == job["job_id"]
    assert (await client.get(f"/api/jobs/{job['job_id']}", headers=headers)).json()["role"] == "Original role"
    assert (await client.get("/api/jobs", headers=headers)).json()["total"] == 1
    assert (await client.get("/api/companies", headers=headers)).json()["total"] == 1


async def test_quick_create_only_fills_empty_details_on_reused_job(client: AsyncClient, headers: dict):
    job = await create_job(client, headers, job_url="https://example.com/1", JD="Original")

    await quick_create(client, headers, job_url="https://example.com/1", JD="New", exp_text="2 years")

    saved = (await client.get(f"/api/jobs/{job['job_id']}", headers=headers)).json()
    assert saved["JD"] == "Original"
    assert saved["exp_text"] == "2 years"


async def test_quick_create_only_fills_empty_details_on_reused_company(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, name="Acme", company_description="Original")

    await quick_create(
        client, headers, company_name="Acme", company_description="New", company_site="https://acme.example.com"
    )

    saved = (await client.get(f"/api/companies/{company['company_id']}", headers=headers)).json()
    assert saved["company_description"] == "Original"
    assert saved["company_site"] == "https://acme.example.com"


async def test_quick_create_details_must_fit_reused_job(client: AsyncClient, headers: dict):
    await create_job(client, headers, job_url="https://example.com/1", exp_min=5)

    response = await client.post(
        "/api/applications/quick", json=quick_payload(job_url="https://example.com/1", exp_max=1), headers=headers
    )

    assert response.status_code == 422


async def test_quick_create_twice_with_same_link(client: AsyncClient, headers: dict):
    await quick_create(client, headers)

    response = await client.post("/api/applications/quick", json=quick_payload(), headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "This user has already applied to this job"


async def test_quick_create_same_link_for_different_users(client: AsyncClient, headers: dict, other_headers: dict):
    mine = await quick_create(client, headers)
    theirs = await quick_create(client, other_headers)

    assert mine["job_id"] != theirs["job_id"]


@pytest.mark.parametrize(
    "changes",
    [
        {"company_name": "   "},
        {"role": "   "},
        {"job_url": "not a url"},
        {"company_site": "not a url"},
        {"current_status": "Hired"},
        {"current_status": None},
        {"interview_rounds": -1},
        {"interview_rounds": 101},
        {"notes": "x" * 5001},
        {"job_url": "https://example.com/" + "x" * 2000},
        {"JD": "x" * 50_001},
        {"exp_max": 1000},
        {"salary_max": "1234567890123456"},
        {"exp_min": 5, "exp_max": 1},
        {"salary_min": 5, "salary_max": 1},
        {"job_posting_date": "2026-02-01", "application_deadline": "2026-01-01"},
        {"salary_currency": "RUPEES"},
    ],
)
async def test_quick_create_invalid_values(client: AsyncClient, headers: dict, changes: dict):
    response = await client.post("/api/applications/quick", json=quick_payload(**changes), headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["company_name", "role", "job_url"])
async def test_quick_create_missing_required_field(client: AsyncClient, headers: dict, field: str):
    body = quick_payload()
    del body[field]

    response = await client.post("/api/applications/quick", json=body, headers=headers)

    assert response.status_code == 422
    assert field in response.text


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("GET", "/history", None),
        ("PATCH", "", {"notes": "Hacked"}),
        ("DELETE", "", None),
    ],
)
async def test_other_users_application_is_404(
    client: AsyncClient, headers: dict, other_headers: dict, method: str, suffix: str, body: dict | None
):
    application = await create_application(client, headers, notes="Mine")
    path = f"/api/applications/{application['application_id']}"

    response = await client.request(method, path + suffix, json=body, headers=other_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"
    assert (await client.get(path, headers=headers)).json()["notes"] == "Mine"


async def test_replace_other_users_application_is_404(client: AsyncClient, headers: dict, other_headers: dict):
    application = await create_application(client, headers)
    their_job = await create_job(client, other_headers)

    response = await client.put(
        f"/api/applications/{application['application_id']}",
        json={"job_id": their_job["job_id"], "date_applied": "2026-03-01"},
        headers=other_headers,
    )

    assert response.status_code == 404
