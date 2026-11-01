from datetime import timedelta

import pytest
from httpx import AsyncClient

from auth import create_access_token
from tests.conftest import (
    auth_header,
    create_company,
    create_job,
    create_lookup,
    create_test_user,
    login_user,
)


pytestmark = pytest.mark.anyio


def is_html(response) -> bool:
    return response.headers["content-type"].startswith("text/html")


@pytest.fixture
async def logged_in(client: AsyncClient) -> dict[str, str]:
    await create_test_user(client)
    return auth_header(await login_user(client))


async def log_in_as_someone_else(client: AsyncClient) -> None:
    await create_test_user(client, username="otheruser", email="other@example.com")
    await login_user(client, email="other@example.com")


@pytest.mark.parametrize("path", ["/", "/login", "/register", "/forgot-password", "/reset-password"])
async def test_public_pages_work_when_logged_out(client: AsyncClient, path: str):
    response = await client.get(path)

    assert response.status_code == 200
    assert is_html(response)


async def test_reset_password_page_doesnt_leak_token(client: AsyncClient):
    response = await client.get("/reset-password?token=secret")

    assert response.headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize(
    ("path", "next_url"),
    [
        ("/jobs", "%2Fjobs"),
        ("/jobs/some-job", "%2Fjobs%2Fsome-job"),
        ("/companies", "%2Fcompanies"),
        ("/companies/some-company", "%2Fcompanies%2Fsome-company"),
        ("/account", "%2Faccount"),
        ("/jobs?q=python", "%2Fjobs%3Fq%3Dpython"),
    ],
)
async def test_private_pages_redirect_to_login(client: AsyncClient, path: str, next_url: str):
    response = await client.get(path)

    assert response.status_code == 303
    assert response.headers["location"] == f"/login?next={next_url}"


async def test_bearer_header_doesnt_open_private_pages(client: AsyncClient):
    await create_test_user(client)
    headers = auth_header(await login_user(client))
    client.cookies.clear()

    response = await client.get("/jobs", headers=headers)

    assert response.status_code == 303


async def test_expired_cookie_redirects_to_login(client: AsyncClient):
    user = await create_test_user(client)
    token = create_access_token({"sub": str(user["id"]), "ver": 0}, expires_delta=timedelta(minutes=-1))
    client.cookies.set("access_token", token)

    response = await client.get("/jobs")

    assert response.status_code == 303


async def test_cookie_stops_working_after_password_change(client: AsyncClient, logged_in: dict):
    old_cookie = client.cookies.get("access_token")
    await client.patch(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "brandnewpassword"},
        headers=logged_in,
    )

    assert (await client.get("/jobs")).status_code == 200

    client.cookies.clear()
    client.cookies.set("access_token", old_cookie)
    assert (await client.get("/jobs")).status_code == 303


async def test_logout_ends_the_page_session(client: AsyncClient, logged_in: dict):
    assert (await client.get("/jobs")).status_code == 200

    await client.post("/api/users/logout")

    assert (await client.get("/jobs")).status_code == 303


@pytest.mark.parametrize("path", ["/jobs", "/companies", "/account"])
async def test_private_pages_work_when_logged_in(client: AsyncClient, logged_in: dict, path: str):
    response = await client.get(path)

    assert response.status_code == 200
    assert is_html(response)


async def test_jobs_page_shows_my_jobs(client: AsyncClient, logged_in: dict):
    await create_job(client, logged_in, role="Backend Engineer")

    response = await client.get("/jobs")

    assert "Backend Engineer" in response.text


async def test_jobs_page_search(client: AsyncClient, logged_in: dict):
    company = await create_company(client, logged_in)
    await create_job(client, logged_in, company["company_id"], role="Platform Wizard", job_url="https://example.com/1")
    await create_job(client, logged_in, company["company_id"], role="Data Analyst", job_url="https://example.com/2")

    response = await client.get("/jobs", params={"q": "analyst"})

    assert "Data Analyst" in response.text
    assert "Platform Wizard" not in response.text


async def test_jobs_page_filter_choices_are_my_own(client: AsyncClient, logged_in: dict):
    await create_lookup(client, logged_in, "/api/locations", "Delhi")
    await create_test_user(client, username="otheruser", email="other@example.com")
    other = auth_header(await login_user(client, email="other@example.com"))
    await create_lookup(client, other, "/api/locations", "Secret City")

    await login_user(client)
    response = await client.get("/jobs")

    assert "Delhi" in response.text
    assert "Secret City" not in response.text


async def test_jobs_page_invalid_filter_shows_error_page(client: AsyncClient, logged_in: dict):
    response = await client.get("/jobs?location_id=abc")

    assert response.status_code == 422
    assert is_html(response)
    assert "Invalid request" in response.text


async def test_job_page(client: AsyncClient, logged_in: dict):
    company = await create_company(client, logged_in, name="Acme Corp")
    job = await create_job(client, logged_in, company["company_id"], role="Backend Engineer", JD="Build great APIs")
    skill = await create_lookup(client, logged_in, "/api/skills", "Python")
    await client.put(
        f"/api/jobs/{job['job_id']}/details", json={"skills": [{"skill_id": skill["id"]}]}, headers=logged_in
    )

    response = await client.get(f"/jobs/{job['job_id']}")

    assert response.status_code == 200
    assert "Backend Engineer" in response.text
    assert "Acme Corp" in response.text
    assert "Build great APIs" in response.text
    assert "Python" in response.text


async def test_job_page_not_found(client: AsyncClient, logged_in: dict):
    response = await client.get("/jobs/nope")

    assert response.status_code == 404
    assert is_html(response)
    assert "Job not found" in response.text


async def test_companies_page_shows_and_searches(client: AsyncClient, logged_in: dict):
    await create_company(client, logged_in, name="Acme Corp")
    await create_company(client, logged_in, name="Globex")

    all_companies = await client.get("/companies")
    searched = await client.get("/companies", params={"q": "globex"})

    assert "Acme Corp" in all_companies.text
    assert "Globex" in all_companies.text
    assert "Globex" in searched.text
    assert "Acme Corp" not in searched.text


async def test_company_page(client: AsyncClient, logged_in: dict):
    company = await create_company(client, logged_in, name="Acme Corp")
    await create_job(client, logged_in, company["company_id"], role="Backend Engineer")
    location = await create_lookup(client, logged_in, "/api/locations", "Delhi")
    await client.put(
        f"/api/companies/{company['company_id']}/locations", json={"location_ids": [location["id"]]}, headers=logged_in
    )

    response = await client.get(f"/companies/{company['company_id']}")

    assert response.status_code == 200
    assert "Acme Corp" in response.text
    assert "Backend Engineer" in response.text
    assert "Delhi" in response.text


async def test_company_page_not_found(client: AsyncClient, logged_in: dict):
    response = await client.get("/companies/nope")

    assert response.status_code == 404
    assert is_html(response)
    assert "Company not found" in response.text


async def test_other_users_job_page_is_404(client: AsyncClient, logged_in: dict):
    job = await create_job(client, logged_in, role="My Secret Role")

    await log_in_as_someone_else(client)
    response = await client.get(f"/jobs/{job['job_id']}")

    assert response.status_code == 404
    assert "My Secret Role" not in response.text


async def test_other_users_company_page_is_404(client: AsyncClient, logged_in: dict):
    company = await create_company(client, logged_in, name="My Secret Company")

    await log_in_as_someone_else(client)
    response = await client.get(f"/companies/{company['company_id']}")

    assert response.status_code == 404
    assert "My Secret Company" not in response.text


async def test_lists_on_pages_are_private(client: AsyncClient, logged_in: dict):
    await create_job(client, logged_in, role="My Secret Role")
    await create_company(client, logged_in, name="My Secret Company")

    await log_in_as_someone_else(client)

    assert "My Secret Role" not in (await client.get("/jobs")).text
    assert "My Secret Company" not in (await client.get("/companies")).text


XSS = "<script>alert('hacked')</script>"


async def test_job_page_escapes_html(client: AsyncClient, logged_in: dict):
    job = await create_job(client, logged_in, role=XSS, JD=XSS)

    for path in ("/jobs", f"/jobs/{job['job_id']}"):
        response = await client.get(path)
        assert response.status_code == 200
        assert "<script>alert(" not in response.text


async def test_company_page_escapes_html(client: AsyncClient, logged_in: dict):
    company = await create_company(client, logged_in, name=XSS, company_description=XSS)

    for path in ("/companies", f"/companies/{company['company_id']}"):
        response = await client.get(path)
        assert response.status_code == 200
        assert "<script>alert(" not in response.text


async def test_search_box_escapes_html(client: AsyncClient, logged_in: dict):
    for path in ("/jobs", "/companies"):
        response = await client.get(path, params={"q": XSS})
        assert response.status_code == 200
        assert "<script>alert(" not in response.text


async def test_unknown_page_shows_html_error(client: AsyncClient):
    response = await client.get("/no-such-page")

    assert response.status_code == 404
    assert is_html(response)


async def test_unknown_api_route_gives_json_error(client: AsyncClient):
    response = await client.get("/api/no-such-route")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"


async def test_static_files_are_rechecked_by_the_browser(client: AsyncClient):
    response = await client.get("/static/css/main.css")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


async def test_other_pages_dont_get_the_static_header(client: AsyncClient):
    response = await client.get("/login")

    assert response.headers.get("cache-control") != "no-cache"


async def test_missing_static_file_gives_json_error(client: AsyncClient):
    response = await client.get("/static/no-such-file.css")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"
