import pytest
from httpx import AsyncClient

from tests.conftest import create_company, create_job, create_lookup


pytestmark = pytest.mark.anyio

LISTS = [
    ("/api/locations", "Location", 100),
    ("/api/work-modes", "Work mode", 30),
    ("/api/skills", "Skill", 100),
    ("/api/education", "Education requirement", 150),
    ("/api/sources", "Source", 50),
]
PATHS = [path for path, _, _ in LISTS]

JOB_DETAILS = {
    "/api/locations": lambda entry_id: {"location_ids": [entry_id]},
    "/api/work-modes": lambda entry_id: {"work_mode_ids": [entry_id]},
    "/api/skills": lambda entry_id: {"skills": [{"skill_id": entry_id}]},
    "/api/education": lambda entry_id: {"education": [{"education_id": entry_id}]},
    "/api/sources": lambda entry_id: {"source_ids": [entry_id]},
}


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize(
    ("method", "suffix"),
    [("GET", ""), ("POST", ""), ("PATCH", "/1"), ("DELETE", "/1")],
)
async def test_lookup_routes_need_login(client: AsyncClient, path: str, method: str, suffix: str):
    response = await client.request(method, path + suffix)

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.parametrize("path", PATHS)
async def test_list_starts_empty(client: AsyncClient, headers: dict, path: str):
    response = await client.get(path, headers=headers)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("path", PATHS)
async def test_create_entry(client: AsyncClient, headers: dict, path: str):
    response = await client.post(path, json={"name": "Something"}, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Something"
    assert isinstance(data["id"], int)


@pytest.mark.parametrize("path", PATHS)
async def test_create_entry_trims_spaces(client: AsyncClient, headers: dict, path: str):
    entry = await create_lookup(client, headers, path, "  Something  ")

    assert entry["name"] == "Something"


@pytest.mark.parametrize(("path", "item_name", "max_length"), LISTS)
async def test_create_entry_name_length(client: AsyncClient, headers: dict, path: str, item_name: str, max_length: int):
    longest = await client.post(path, json={"name": "x" * max_length}, headers=headers)
    too_long = await client.post(path, json={"name": "y" * (max_length + 1)}, headers=headers)

    assert longest.status_code == 201
    assert too_long.status_code == 422


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": "   "}, {"name": None}])
async def test_create_entry_invalid_name(client: AsyncClient, headers: dict, path: str, body: dict):
    response = await client.post(path, json=body, headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize(("path", "item_name", "_"), LISTS)
@pytest.mark.parametrize("name", ["Python", "PYTHON"])
async def test_create_entry_duplicate_ignores_case(
    client: AsyncClient, headers: dict, path: str, item_name: str, _: int, name: str
):
    await create_lookup(client, headers, path, "Python")

    response = await client.post(path, json={"name": name}, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == f"This {item_name.lower()} already exists"


@pytest.mark.parametrize("path", PATHS)
async def test_list_sorted_ignoring_case(client: AsyncClient, headers: dict, path: str):
    for name in ["banana", "Cherry", "apple"]:
        await create_lookup(client, headers, path, name)

    response = await client.get(path, headers=headers)

    assert [entry["name"] for entry in response.json()] == ["apple", "banana", "Cherry"]


@pytest.mark.parametrize("path", PATHS)
async def test_rename_entry(client: AsyncClient, headers: dict, path: str):
    entry = await create_lookup(client, headers, path, "Old")

    response = await client.patch(f"{path}/{entry['id']}", json={"name": "  New  "}, headers=headers)

    assert response.status_code == 200
    assert response.json() == {"id": entry["id"], "name": "New"}


@pytest.mark.parametrize("path", PATHS)
async def test_rename_entry_can_change_only_the_case(client: AsyncClient, headers: dict, path: str):
    entry = await create_lookup(client, headers, path, "python")

    response = await client.patch(f"{path}/{entry['id']}", json={"name": "Python"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Python"


@pytest.mark.parametrize("path", PATHS)
async def test_rename_entry_to_a_taken_name(client: AsyncClient, headers: dict, path: str):
    await create_lookup(client, headers, path, "Taken")
    entry = await create_lookup(client, headers, path, "Other")

    response = await client.patch(f"{path}/{entry['id']}", json={"name": "taken"}, headers=headers)

    assert response.status_code == 409


@pytest.mark.parametrize("path", PATHS)
async def test_rename_entry_invalid_name(client: AsyncClient, headers: dict, path: str):
    entry = await create_lookup(client, headers, path, "Old")

    response = await client.patch(f"{path}/{entry['id']}", json={"name": "  "}, headers=headers)

    assert response.status_code == 422


@pytest.mark.parametrize(("path", "item_name", "_"), LISTS)
async def test_rename_entry_not_found(client: AsyncClient, headers: dict, path: str, item_name: str, _: int):
    response = await client.patch(f"{path}/999999", json={"name": "New"}, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == f"{item_name} not found"


@pytest.mark.parametrize("path", PATHS)
async def test_rename_entry_in_use_is_allowed(client: AsyncClient, headers: dict, path: str):
    job = await create_job(client, headers)
    entry = await create_lookup(client, headers, path, "Typoo")
    await client.put(f"/api/jobs/{job['job_id']}/details", json=JOB_DETAILS[path](entry["id"]), headers=headers)

    response = await client.patch(f"{path}/{entry['id']}", json={"name": "Typo"}, headers=headers)

    assert response.status_code == 200
    assert "Typo" in (await client.get(f"/api/jobs/{job['job_id']}/details", headers=headers)).text
    assert "Typoo" not in (await client.get(f"/api/jobs/{job['job_id']}/details", headers=headers)).text


@pytest.mark.parametrize("path", PATHS)
async def test_delete_entry(client: AsyncClient, headers: dict, path: str):
    entry = await create_lookup(client, headers, path, "Something")

    response = await client.delete(f"{path}/{entry['id']}", headers=headers)

    assert response.status_code == 204
    assert (await client.get(path, headers=headers)).json() == []


@pytest.mark.parametrize("path", PATHS)
async def test_delete_entry_not_found(client: AsyncClient, headers: dict, path: str):
    response = await client.delete(f"{path}/999999", headers=headers)

    assert response.status_code == 404


@pytest.mark.parametrize("path", PATHS)
async def test_delete_entry_used_by_a_job_is_refused(client: AsyncClient, headers: dict, path: str):
    job = await create_job(client, headers)
    entry = await create_lookup(client, headers, path, "Something")
    await client.put(f"/api/jobs/{job['job_id']}/details", json=JOB_DETAILS[path](entry["id"]), headers=headers)

    response = await client.delete(f"{path}/{entry['id']}", headers=headers)

    assert response.status_code == 409
    assert "remove it there first" in response.json()["detail"]


async def test_delete_location_used_by_a_company_is_refused(client: AsyncClient, headers: dict):
    company = await create_company(client, headers)
    location = await create_lookup(client, headers, "/api/locations", "Delhi")
    await client.put(
        f"/api/companies/{company['company_id']}/locations", json={"location_ids": [location["id"]]}, headers=headers
    )

    response = await client.delete(f"/api/locations/{location['id']}", headers=headers)

    assert response.status_code == 409


@pytest.mark.parametrize("path", PATHS)
async def test_lists_are_private(client: AsyncClient, headers: dict, other_headers: dict, path: str):
    await create_lookup(client, headers, path, "Mine")

    response = await client.get(path, headers=other_headers)

    assert response.json() == []


@pytest.mark.parametrize("path", PATHS)
async def test_different_users_can_use_the_same_name(
    client: AsyncClient, headers: dict, other_headers: dict, path: str
):
    mine = await create_lookup(client, headers, path, "Python")
    theirs = await create_lookup(client, other_headers, path, "Python")

    assert mine["id"] != theirs["id"]


@pytest.mark.parametrize(("path", "item_name", "_"), LISTS)
@pytest.mark.parametrize(("method", "body"), [("PATCH", {"name": "Hacked"}), ("DELETE", None)])
async def test_other_users_entry_is_404(
    client: AsyncClient,
    headers: dict,
    other_headers: dict,
    path: str,
    item_name: str,
    _: int,
    method: str,
    body: dict | None,
):
    entry = await create_lookup(client, headers, path, "Mine")

    response = await client.request(method, f"{path}/{entry['id']}", json=body, headers=other_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == f"{item_name} not found"
    assert (await client.get(path, headers=headers)).json() == [entry]
