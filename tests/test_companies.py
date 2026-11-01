import pytest
from httpx import AsyncClient

from tests.conftest import create_company, create_job, create_lookup


pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/companies"),
        ("POST", "/api/companies"),
        ("GET", "/api/companies/acme"),
        ("PUT", "/api/companies/acme"),
        ("PATCH", "/api/companies/acme"),
        ("DELETE", "/api/companies/acme"),
        ("GET", "/api/companies/acme/locations"),
        ("PUT", "/api/companies/acme/locations"),
    ],
)
async def test_company_routes_need_login(client: AsyncClient, method: str, path: str):
    response = await client.request(method, path)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


async def test_get_companies_empty(client: AsyncClient, headers: dict):
    response = await client.get("/api/companies", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["companies"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


async def test_get_companies_with_pagination(client: AsyncClient, headers: dict):
    for i in range(5):
        await create_company(client, headers, name=f"Company {i}")

    data = (await client.get("/api/companies", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["companies"]) == 5
    assert data["has_more"] is False

    data = (await client.get("/api/companies?limit=2", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["companies"]) == 2
    assert data["has_more"] is True

    data = (await client.get("/api/companies?skip=4&limit=2", headers=headers)).json()
    assert data["total"] == 5
    assert len(data["companies"]) == 1
    assert data["skip"] == 4
    assert data["limit"] == 2
    assert data["has_more"] is False


@pytest.mark.parametrize("query", ["skip=-1", "limit=0", "limit=101", f"q={'x' * 101}"])
async def test_get_companies_invalid_query(client: AsyncClient, headers: dict, query: str):
    response = await client.get(f"/api/companies?{query}", headers=headers)

    assert response.status_code == 422


async def test_get_companies_sorted_by_name(client: AsyncClient, headers: dict):
    for name in ["Zeta", "Acme", "Mango"]:
        await create_company(client, headers, name=name)

    data = (await client.get("/api/companies", headers=headers)).json()

    assert [company["company_name"] for company in data["companies"]] == ["Acme", "Mango", "Zeta"]


@pytest.mark.parametrize(
    ("q", "expected"), [("goo", ["Google"]), ("GOOGLE", ["Google"]), ("   ", ["Amazon", "Google"])]
)
async def test_get_companies_search(client: AsyncClient, headers: dict, q: str, expected: list[str]):
    await create_company(client, headers, name="Google")
    await create_company(client, headers, name="Amazon")

    response = await client.get("/api/companies", params={"q": q}, headers=headers)

    assert [company["company_name"] for company in response.json()["companies"]] == expected
    assert response.json()["total"] == len(expected)


async def test_get_companies_search_treats_wildcards_literally(client: AsyncClient, headers: dict):
    await create_company(client, headers, name="100% Tech")
    await create_company(client, headers, name="Other")

    response = await client.get("/api/companies", params={"q": "%"}, headers=headers)

    assert [company["company_name"] for company in response.json()["companies"]] == ["100% Tech"]


async def test_get_companies_only_shows_my_own(client: AsyncClient, headers: dict, other_headers: dict):
    await create_company(client, headers, name="Mine")
    await create_company(client, other_headers, name="Theirs")

    data = (await client.get("/api/companies", headers=headers)).json()

    assert data["total"] == 1
    assert data["companies"][0]["company_name"] == "Mine"


async def test_create_company_success(client: AsyncClient, headers: dict):
    response = await client.post(
        "/api/companies",
        json={
            "company_name": "Google India",
            "company_site": "https://google.co.in",
            "company_description": "Search",
        },
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == "google-india"
    assert data["company_name"] == "Google India"
    assert data["company_site"] == "https://google.co.in"
    assert data["company_description"] == "Search"


async def test_create_company_only_name_is_required(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)

    assert company["company_site"] is None
    assert company["company_description"] is None


async def test_create_company_same_name_gets_new_id(client: AsyncClient, headers: dict, other_headers: dict):
    first = await create_company(client, headers, name="Google")
    second = await create_company(client, headers, name="Google")
    third = await create_company(client, other_headers, name="Google")

    assert [first["company_id"], second["company_id"], third["company_id"]] == ["google", "google-2", "google-3"]


async def test_create_company_name_without_letters_gets_fallback_id(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, name="!!!")

    assert company["company_id"] == "company"


async def test_create_company_ignores_a_sent_id(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, name="Google", company_id="my-own-id")

    assert company["company_id"] == "google"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"company_name": ""},
        {"company_name": "x" * 256},
        {"company_name": "Acme", "company_site": "not a url"},
        {"company_name": "Acme", "company_site": "javascript:alert(1)"},
        {"company_name": "Acme", "company_site": "ftp://example.com"},
    ],
)
async def test_create_company_invalid(client: AsyncClient, headers: dict, body: dict):
    response = await client.post("/api/companies", json=body, headers=headers)

    assert response.status_code == 422


async def test_get_company(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)

    response = await client.get(f"/api/companies/{company['company_id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == company


async def test_get_company_not_found(client: AsyncClient, headers: dict):
    response = await client.get("/api/companies/nope", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"


async def test_update_company_only_changes_what_was_sent(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, company_description="Original")

    response = await client.patch(
        f"/api/companies/{company['company_id']}", json={"company_name": "Renamed"}, headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "Renamed"
    assert data["company_description"] == "Original"
    assert data["company_id"] == company["company_id"]


async def test_update_company_can_clear_optional_field(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, company_site="https://example.com")

    response = await client.patch(
        f"/api/companies/{company['company_id']}", json={"company_site": None}, headers=headers
    )

    assert response.json()["company_site"] is None


@pytest.mark.parametrize("body", [{"company_name": None}, {"company_name": ""}, {"company_site": "not a url"}])
async def test_update_company_invalid(client: AsyncClient, headers: dict, body: dict):
    company = await create_company(client, headers)

    response = await client.patch(f"/api/companies/{company['company_id']}", json=body, headers=headers)

    assert response.status_code == 422


async def test_replace_company_clears_fields_left_out(client: AsyncClient, headers: dict):
    company = await create_company(client, headers, company_description="Original")

    response = await client.put(
        f"/api/companies/{company['company_id']}", json={"company_name": "New"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["company_name"] == "New"
    assert response.json()["company_description"] is None


async def test_replace_company_needs_name(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)

    response = await client.put(f"/api/companies/{company['company_id']}", json={}, headers=headers)

    assert response.status_code == 422


async def test_delete_company(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)

    response = await client.delete(f"/api/companies/{company['company_id']}", headers=headers)

    assert response.status_code == 204
    assert (await client.get(f"/api/companies/{company['company_id']}", headers=headers)).status_code == 404


async def test_delete_company_with_jobs_is_refused(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    await create_job(client, headers, company["company_id"])

    response = await client.delete(f"/api/companies/{company['company_id']}", headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Company has related jobs and cannot be deleted"


async def test_delete_company_removes_its_location_links(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    location = await create_lookup(client, headers, "/api/locations", "Delhi")
    await client.put(
        f"/api/companies/{company['company_id']}/locations", json={"location_ids": [location["id"]]}, headers=headers
    )

    response = await client.delete(f"/api/companies/{company['company_id']}", headers=headers)
    assert response.status_code == 204

    response = await client.delete(f"/api/locations/{location['id']}", headers=headers)
    assert response.status_code == 204


async def test_company_locations_start_empty(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)

    response = await client.get(f"/api/companies/{company['company_id']}/locations", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_replace_company_locations(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    path = f"/api/companies/{company['company_id']}/locations"
    pune = await create_lookup(client, headers, "/api/locations", "Pune")
    delhi = await create_lookup(client, headers, "/api/locations", "Delhi")

    response = await client.put(path, json={"location_ids": [pune["id"], delhi["id"]]}, headers=headers)
    assert response.status_code == 200
    assert response.json() == [delhi, pune]

    response = await client.put(path, json={"location_ids": [pune["id"]]}, headers=headers)
    assert response.json() == [pune]

    response = await client.put(path, json={"location_ids": []}, headers=headers)
    assert response.json() == []
    assert (await client.get(path, headers=headers)).json() == []


async def test_replace_company_locations_unknown_id(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)

    response = await client.put(
        f"/api/companies/{company['company_id']}/locations", json={"location_ids": [999999]}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Location not found: 999999"


async def test_replace_company_locations_duplicate_id(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    location = await create_lookup(client, headers, "/api/locations", "Delhi")

    response = await client.put(
        f"/api/companies/{company['company_id']}/locations",
        json={"location_ids": [location["id"], location["id"]]},
        headers=headers,
    )

    assert response.status_code == 422


async def test_replace_company_locations_with_someone_elses_location(
    client: AsyncClient, headers: dict, other_headers: dict
):
    company = await create_company(client, headers)
    their_location = await create_lookup(client, other_headers, "/api/locations", "Delhi")

    response = await client.put(
        f"/api/companies/{company['company_id']}/locations",
        json={"location_ids": [their_location["id"]]},
        headers=headers,
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("PUT", "", {"company_name": "Hacked"}),
        ("PATCH", "", {"company_name": "Hacked"}),
        ("DELETE", "", None),
        ("GET", "/locations", None),
        ("PUT", "/locations", {"location_ids": []}),
    ],
)
async def test_other_users_company_is_404(
    client: AsyncClient, headers: dict, other_headers: dict, method: str, suffix: str, body: dict | None
):
    company = await create_company(client, headers, name="Mine")
    path = f"/api/companies/{company['company_id']}"

    response = await client.request(method, path + suffix, json=body, headers=other_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Company not found"
    assert (await client.get(path, headers=headers)).json()["company_name"] == "Mine"
