"""Tests for /api/applications."""

from conftest import make_user


def create_application(client, headers, job_id) -> int:
    """Create an application for the logged-in user and return its id."""

    response = client.post("/api/applications", json={"job_id": job_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["application_id"]


# Applications are private: without logging in you can't list or create them.
def test_applications_require_login(client, job):
    assert client.get("/api/applications").status_code == 401
    assert client.post("/api/applications", json={"job_id": job["job_id"]}).status_code == 401


# The owner can create, list, view, edit (PATCH), replace (PUT) and delete their application.
def test_owner_can_manage_own_application(client, rudra, job):
    _, headers = rudra
    application_id = create_application(client, headers, job["job_id"])
    url = f"/api/applications/{application_id}"

    listed = client.get("/api/applications", headers=headers).json()
    assert application_id in [a["application_id"] for a in listed]
    assert client.get(url, headers=headers).status_code == 200

    edited = client.patch(url, json={"current_status": "Interview"}, headers=headers)
    assert edited.status_code == 200
    assert edited.json()["current_status"] == "Interview"

    replaced = client.put(
        url, json={"job_id": job["job_id"], "date_applied": "2026-10-20", "current_status": "Screening"}, headers=headers
    )
    assert replaced.status_code == 200
    assert replaced.json()["current_status"] == "Screening"

    assert client.delete(url, headers=headers).status_code == 204
    assert client.get(url, headers=headers).status_code == 404


# Another user can't see, edit, replace or delete your application (403),
# and it doesn't show up in their list.
def test_other_user_cannot_access_application(client, rudra, aman, job):
    _, rudra_headers = rudra
    _, aman_headers = aman
    application_id = create_application(client, rudra_headers, job["job_id"])
    url = f"/api/applications/{application_id}"

    try:
        aman_list = client.get("/api/applications", headers=aman_headers).json()
        assert application_id not in [a["application_id"] for a in aman_list]

        assert client.get(url, headers=aman_headers).status_code == 403
        assert client.patch(url, json={"current_status": "Rejected"}, headers=aman_headers).status_code == 403
        assert client.put(url, json={"job_id": job["job_id"], "date_applied": "2026-10-20"}, headers=aman_headers).status_code == 403
        assert client.delete(url, headers=aman_headers).status_code == 403

        # Still there and unchanged for Rudra.
        assert client.get(url, headers=rudra_headers).json()["current_status"] == "Applied"
    finally:
        # "finally" runs even if a check above failed, so the test data is always cleaned up.
        client.delete(url, headers=rudra_headers)


# Opening an application that doesn't exist gives 404.
def test_unknown_application_is_404(client, aman):
    _, headers = aman
    assert client.get("/api/applications/999999999", headers=headers).status_code == 404


# Two different users can apply to the same job, but one user can't apply to it twice (409).
def test_same_job_once_per_user(client, rudra, aman, job):
    _, rudra_headers = rudra
    _, aman_headers = aman
    rudra_application = create_application(client, rudra_headers, job["job_id"])
    aman_application = create_application(client, aman_headers, job["job_id"])

    try:
        duplicate = client.post("/api/applications", json={"job_id": job["job_id"]}, headers=rudra_headers)
        assert duplicate.status_code == 409
    finally:
        client.delete(f"/api/applications/{rudra_application}", headers=rudra_headers)
        client.delete(f"/api/applications/{aman_application}", headers=aman_headers)


# Deleting a user also deletes their applications.
def test_deleting_user_deletes_their_applications(client, aman, job):
    _, temp_headers = make_user(client, "temp")
    application_id = create_application(client, temp_headers, job["job_id"])

    assert client.delete("/api/users/me", headers=temp_headers).status_code == 204

    # 404 (gone), not 403 (which would mean it still exists and belongs to someone else).
    _, aman_headers = aman
    assert client.get(f"/api/applications/{application_id}", headers=aman_headers).status_code == 404
