from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, patch

import pytest
from botocore.exceptions import ClientError
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import models
from auth import create_access_token, hash_reset_token
from config import settings
from tests.conftest import (
    auth_header,
    create_application,
    create_lookup,
    create_test_user,
    login_user,
    make_image_bytes,
)


pytestmark = pytest.mark.anyio


def upload(image_bytes: bytes, filename: str = "profile.jpg", content_type: str = "image/jpeg") -> dict:
    return {"file": (filename, BytesIO(image_bytes), content_type)}


async def count_rows(db_session: AsyncSession, model) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar()


async def test_create_user_success(client: AsyncClient):
    response = await client.post(
        "/api/users",
        json={"username": "newuser", "email": "newuser@example.com", "password": "securepassword123"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "id" in data
    assert data["image_file"] is None
    assert data["image_path"] is None
    assert "password" not in data
    assert "password_hash" not in data


async def test_create_user_saves_a_hash_not_the_password(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(client, password="securepassword123")

    saved = await db_session.get(models.User, user["id"])

    assert saved.password_hash != "securepassword123"
    assert saved.password_hash.startswith("$argon2")


async def test_create_user_lowercases_email(client: AsyncClient):
    user = await create_test_user(client, email="MixedCase@Example.com")

    assert user["email"] == "mixedcase@example.com"


async def test_create_user_missing_fields(client: AsyncClient):
    response = await client.post("/api/users", json={"username": "testuser"})

    assert response.status_code == 422
    assert "email" in response.text
    assert "password" in response.text


@pytest.mark.parametrize(
    "changes",
    [
        {"username": ""},
        {"username": "x" * 51},
        {"email": "not-an-email"},
        {"password": "short"},
        {"password": "x" * 129},
    ],
)
async def test_create_user_invalid_values(client: AsyncClient, changes: dict):
    valid = {"username": "newuser", "email": "newuser@example.com", "password": "securepassword123"}

    response = await client.post("/api/users", json=valid | changes)

    assert response.status_code == 422


@pytest.mark.parametrize("email", ["test@example.com", "TEST@example.com"])
async def test_create_user_duplicate_email(client: AsyncClient, email: str):
    await create_test_user(client)

    response = await client.post(
        "/api/users", json={"username": "different_user", "email": email, "password": "password123"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


@pytest.mark.parametrize("username", ["testuser", "TestUser"])
async def test_create_user_duplicate_username(client: AsyncClient, username: str):
    await create_test_user(client)

    response = await client.post(
        "/api/users", json={"username": username, "email": "different@example.com", "password": "password123"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Username already exists"


async def test_login_success(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token", data={"username": "test@example.com", "password": "testpassword123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]


async def test_login_sets_http_only_cookie(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token", data={"username": "test@example.com", "password": "testpassword123"}
    )

    cookie = response.headers["set-cookie"].lower()
    assert cookie.startswith("access_token=")
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


async def test_login_email_ignores_case(client: AsyncClient):
    await create_test_user(client)

    response = await client.post(
        "/api/users/token", data={"username": "TEST@EXAMPLE.COM", "password": "testpassword123"}
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("email", "password"),
    [("test@example.com", "wrongpassword"), ("nobody@example.com", "testpassword123")],
)
async def test_login_failure_gives_same_message(client: AsyncClient, email: str, password: str):
    await create_test_user(client)

    response = await client.post("/api/users/token", data={"username": email, "password": password})

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


async def test_login_missing_fields(client: AsyncClient):
    response = await client.post("/api/users/token", data={})

    assert response.status_code == 422


async def test_get_me_success(client: AsyncClient, headers: dict):
    response = await client.get("/api/users/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"
    assert "password_hash" not in data


async def test_get_me_not_logged_in(client: AsyncClient):
    response = await client.get("/api/users/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


async def test_api_ignores_login_cookie(client: AsyncClient):
    await create_test_user(client)
    await login_user(client)
    assert client.cookies.get("access_token")

    response = await client.get("/api/users/me")

    assert response.status_code == 401


async def test_get_me_garbage_token(client: AsyncClient):
    response = await client.get("/api/users/me", headers=auth_header("not-a-real-token"))

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


async def test_get_me_expired_token(client: AsyncClient):
    user = await create_test_user(client)
    token = create_access_token({"sub": str(user["id"]), "ver": 0}, expires_delta=timedelta(minutes=-1))

    response = await client.get("/api/users/me", headers=auth_header(token))

    assert response.status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "1"},
        {"ver": 0},
        {"sub": "not-a-number", "ver": 0},
        {"sub": "999999", "ver": 0},
    ],
)
async def test_get_me_bad_token_contents(client: AsyncClient, claims: dict):
    response = await client.get("/api/users/me", headers=auth_header(create_access_token(claims)))

    assert response.status_code == 401


async def test_get_me_tampered_token(client: AsyncClient):
    user = await create_test_user(client)
    token = create_access_token({"sub": str(user["id"]), "ver": 0})

    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    response = await client.get("/api/users/me", headers=auth_header(tampered))

    assert response.status_code == 401


async def test_update_me(client: AsyncClient, headers: dict):
    response = await client.patch(
        "/api/users/me", json={"username": "renamed", "email": "New@Example.com"}, headers=headers
    )

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "renamed"
    assert data["email"] == "new@example.com"


async def test_update_me_only_changes_what_was_sent(client: AsyncClient, headers: dict):
    response = await client.patch("/api/users/me", json={"username": "renamed"}, headers=headers)

    assert response.json()["email"] == "test@example.com"


async def test_update_me_can_keep_own_name_and_email(client: AsyncClient, headers: dict):
    response = await client.patch(
        "/api/users/me", json={"username": "TESTUSER", "email": "test@example.com"}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["username"] == "TESTUSER"


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"username": "otheruser"}, "Username already exists"),
        ({"email": "other@example.com"}, "Email already registered"),
    ],
)
async def test_update_me_taken_by_someone_else(
    client: AsyncClient, headers: dict, other_headers: dict, changes: dict, detail: str
):
    response = await client.patch("/api/users/me", json=changes, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == detail


@pytest.mark.parametrize("changes", [{"username": None}, {"email": None}, {"username": ""}, {"email": "nope"}])
async def test_update_me_invalid_values(client: AsyncClient, headers: dict, changes: dict):
    response = await client.patch("/api/users/me", json=changes, headers=headers)

    assert response.status_code == 422


async def test_update_me_not_logged_in(client: AsyncClient):
    response = await client.patch("/api/users/me", json={"username": "renamed"})

    assert response.status_code == 401


async def test_change_password(client: AsyncClient, headers: dict):
    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "brandnewpassword"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Password changed successfully"

    await login_user(client, password="brandnewpassword")
    old_login = await client.post(
        "/api/users/token", data={"username": "test@example.com", "password": "testpassword123"}
    )
    assert old_login.status_code == 401


async def test_change_password_logs_out_old_tokens(client: AsyncClient, headers: dict):
    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "brandnewpassword"},
        headers=headers,
    )

    assert (await client.get("/api/users/me", headers=headers)).status_code == 401
    new_headers = auth_header(response.json()["access_token"])
    assert (await client.get("/api/users/me", headers=new_headers)).status_code == 200


async def test_change_password_wrong_current_password(client: AsyncClient, headers: dict):
    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": "wrongpassword", "new_password": "brandnewpassword"},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"
    await login_user(client)


async def test_change_password_too_short(client: AsyncClient, headers: dict):
    response = await client.patch(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "short"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_change_password_cancels_reset_links(client: AsyncClient, headers: dict, mock_send_email: AsyncMock):
    await client.post("/api/users/forgot-password", json={"email": "test@example.com"})
    token = mock_send_email.call_args.kwargs["token"]

    await client.patch(
        "/api/users/me/password",
        json={"current_password": "testpassword123", "new_password": "brandnewpassword"},
        headers=headers,
    )
    response = await client.post("/api/users/reset-password", json={"token": token, "new_password": "anotherpassword"})

    assert response.status_code == 400


async def test_delete_me(client: AsyncClient, headers: dict):
    response = await client.delete("/api/users/me", headers=headers)

    assert response.status_code == 204
    assert (await client.get("/api/users/me", headers=headers)).status_code == 401
    login = await client.post("/api/users/token", data={"username": "test@example.com", "password": "testpassword123"})
    assert login.status_code == 401


async def test_delete_me_removes_all_my_data(
    client: AsyncClient, db_session: AsyncSession, headers: dict, other_headers: dict
):
    application = await create_application(client, headers)
    skill = await create_lookup(client, headers, "/api/skills", "Python")
    await client.put(
        f"/api/jobs/{application['job_id']}/details", json={"skills": [{"skill_id": skill["id"]}]}, headers=headers
    )
    await create_application(client, other_headers)
    await create_lookup(client, other_headers, "/api/skills", "Python")

    response = await client.delete("/api/users/me", headers=headers)

    assert response.status_code == 204
    for model in (models.User, models.Company, models.Job, models.Application, models.Skill):
        assert await count_rows(db_session, model) == 1, model.__name__
    assert await count_rows(db_session, models.JobSkill) == 0
    assert await count_rows(db_session, models.ApplicationStatusChange) == 1


async def test_delete_me_removes_picture_from_s3(client: AsyncClient, headers: dict, mocked_aws):
    await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)

    await client.delete("/api/users/me", headers=headers)

    assert "Contents" not in mocked_aws.list_objects_v2(Bucket="test-bucket")


async def test_upload_profile_picture(client: AsyncClient, headers: dict, mocked_aws):
    response = await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["image_file"].endswith(".jpg")
    assert data["image_path"] == (f"https://test-bucket.s3.us-east-1.amazonaws.com/profile_pics/{data['image_file']}")

    s3_objects = mocked_aws.list_objects_v2(Bucket="test-bucket")
    assert [item["Key"] for item in s3_objects["Contents"]] == [f"profile_pics/{data['image_file']}"]


async def test_upload_profile_picture_is_resized_to_jpeg(client: AsyncClient, headers: dict, mocked_aws):
    image = make_image_bytes("PNG", size=(800, 200), mode="RGBA")

    response = await client.patch(
        "/api/users/me/picture", files=upload(image, "profile.png", "image/png"), headers=headers
    )

    assert response.status_code == 200
    stored = mocked_aws.get_object(Bucket="test-bucket", Key=f"profile_pics/{response.json()['image_file']}")
    assert stored["ContentType"] == "image/jpeg"
    with Image.open(BytesIO(stored["Body"].read())) as saved:
        assert saved.format == "JPEG"
        assert saved.size == (300, 300)


async def test_upload_new_picture_replaces_old_one(client: AsyncClient, headers: dict, mocked_aws):
    first = await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)
    second = await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)

    assert first.json()["image_file"] != second.json()["image_file"]
    s3_objects = mocked_aws.list_objects_v2(Bucket="test-bucket")
    assert [item["Key"] for item in s3_objects["Contents"]] == [f"profile_pics/{second.json()['image_file']}"]


async def test_upload_picture_not_an_image(client: AsyncClient, headers: dict, mocked_aws):
    response = await client.patch(
        "/api/users/me/picture", files=upload(b"this is not an image", "notes.txt", "text/plain"), headers=headers
    )

    assert response.status_code == 400
    assert "Invalid image file" in response.json()["detail"]
    assert "Contents" not in mocked_aws.list_objects_v2(Bucket="test-bucket")


async def test_upload_picture_cut_off_image(client: AsyncClient, headers: dict):
    image = make_image_bytes()

    response = await client.patch("/api/users/me/picture", files=upload(image[: len(image) // 2]), headers=headers)

    assert response.status_code == 400


async def test_upload_picture_too_large(client: AsyncClient, headers: dict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "max_upload_size_bytes", 100)

    response = await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)

    assert response.status_code == 400
    assert "File too large" in response.json()["detail"]


async def test_upload_picture_decompression_bomb(client: AsyncClient, headers: dict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)

    response = await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)

    assert response.status_code == 400
    assert "dimensions are too large" in response.json()["detail"]


async def test_upload_picture_s3_failure_keeps_old_picture(client: AsyncClient, headers: dict, mocked_aws):
    first = await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)
    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "PutObject")

    with patch("routers.users.upload_profile_image", new_callable=AsyncMock, side_effect=error):
        response = await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)

    assert response.status_code == 500
    me = await client.get("/api/users/me", headers=headers)
    assert me.json()["image_file"] == first.json()["image_file"]


async def test_upload_picture_not_logged_in(client: AsyncClient):
    response = await client.patch("/api/users/me/picture", files=upload(make_image_bytes()))

    assert response.status_code == 401


async def test_delete_picture(client: AsyncClient, headers: dict, mocked_aws):
    await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)

    response = await client.delete("/api/users/me/picture", headers=headers)

    assert response.status_code == 200
    assert response.json()["image_file"] is None
    assert response.json()["image_path"] is None
    assert "Contents" not in mocked_aws.list_objects_v2(Bucket="test-bucket")


async def test_delete_picture_when_there_is_none(client: AsyncClient, headers: dict):
    response = await client.delete("/api/users/me/picture", headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "No profile picture to delete"


async def test_forgot_password_sends_email(client: AsyncClient, mock_send_email: AsyncMock):
    await create_test_user(client)

    response = await client.post("/api/users/forgot-password", json={"email": "TEST@example.com"})

    assert response.status_code == 202
    mock_send_email.assert_awaited_once()
    call_kwargs = mock_send_email.call_args.kwargs
    assert call_kwargs["to_email"] == "test@example.com"
    assert call_kwargs["username"] == "testuser"
    assert call_kwargs["token"]


async def test_forgot_password_unknown_email_looks_the_same(client: AsyncClient, mock_send_email: AsyncMock):
    await create_test_user(client)
    known = await client.post("/api/users/forgot-password", json={"email": "test@example.com"})
    mock_send_email.reset_mock()

    unknown = await client.post("/api/users/forgot-password", json={"email": "nobody@example.com"})

    assert unknown.status_code == 202
    assert unknown.json() == known.json()
    mock_send_email.assert_not_called()


async def test_forgot_password_stores_only_a_hash(
    client: AsyncClient, db_session: AsyncSession, mock_send_email: AsyncMock
):
    await create_test_user(client)

    await client.post("/api/users/forgot-password", json={"email": "test@example.com"})

    token = mock_send_email.call_args.kwargs["token"]
    saved = (await db_session.execute(select(models.PasswordResetToken))).scalar_one()
    assert saved.token_hash == hash_reset_token(token)
    assert saved.token_hash != token


async def test_forgot_password_only_newest_link_works(client: AsyncClient, mock_send_email: AsyncMock):
    await create_test_user(client)
    await client.post("/api/users/forgot-password", json={"email": "test@example.com"})
    first_token = mock_send_email.call_args.kwargs["token"]
    await client.post("/api/users/forgot-password", json={"email": "test@example.com"})
    second_token = mock_send_email.call_args.kwargs["token"]

    old_link = await client.post(
        "/api/users/reset-password", json={"token": first_token, "new_password": "brandnewpassword"}
    )
    new_link = await client.post(
        "/api/users/reset-password", json={"token": second_token, "new_password": "brandnewpassword"}
    )

    assert old_link.status_code == 400
    assert new_link.status_code == 200


async def test_forgot_password_cleans_up_expired_tokens(
    client: AsyncClient, db_session: AsyncSession, mock_send_email: AsyncMock
):
    await create_test_user(client)
    await client.post("/api/users/forgot-password", json={"email": "test@example.com"})
    await db_session.execute(
        update(models.PasswordResetToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )

    await client.post("/api/users/forgot-password", json={"email": "nobody@example.com"})

    assert await count_rows(db_session, models.PasswordResetToken) == 0


async def test_forgot_password_invalid_email(client: AsyncClient):
    response = await client.post("/api/users/forgot-password", json={"email": "not-an-email"})

    assert response.status_code == 422


async def test_reset_password(client: AsyncClient, headers: dict, mock_send_email: AsyncMock):
    await client.post("/api/users/forgot-password", json={"email": "test@example.com"})
    token = mock_send_email.call_args.kwargs["token"]

    response = await client.post("/api/users/reset-password", json={"token": token, "new_password": "brandnewpassword"})

    assert response.status_code == 200
    await login_user(client, password="brandnewpassword")
    assert (await client.get("/api/users/me", headers=headers)).status_code == 401


async def test_reset_password_token_works_only_once(client: AsyncClient, mock_send_email: AsyncMock):
    await create_test_user(client)
    await client.post("/api/users/forgot-password", json={"email": "test@example.com"})
    token = mock_send_email.call_args.kwargs["token"]

    await client.post("/api/users/reset-password", json={"token": token, "new_password": "brandnewpassword"})
    response = await client.post("/api/users/reset-password", json={"token": token, "new_password": "anotherpassword"})

    assert response.status_code == 400


async def test_reset_password_invalid_token(client: AsyncClient):
    response = await client.post(
        "/api/users/reset-password", json={"token": "made-up", "new_password": "brandnewpassword"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired reset token"


async def test_reset_password_expired_token(client: AsyncClient, db_session: AsyncSession, mock_send_email: AsyncMock):
    await create_test_user(client)
    await client.post("/api/users/forgot-password", json={"email": "test@example.com"})
    token = mock_send_email.call_args.kwargs["token"]
    await db_session.execute(
        update(models.PasswordResetToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )

    response = await client.post("/api/users/reset-password", json={"token": token, "new_password": "brandnewpassword"})

    assert response.status_code == 400
    assert await count_rows(db_session, models.PasswordResetToken) == 0
    await login_user(client)


async def test_reset_password_too_short(client: AsyncClient):
    response = await client.post("/api/users/reset-password", json={"token": "anything", "new_password": "short"})

    assert response.status_code == 422


async def test_start_page_session_sets_cookie(client: AsyncClient, headers: dict):
    response = await client.post("/api/users/session", headers=headers)

    assert response.status_code == 204
    token = headers["Authorization"].removeprefix("Bearer ")
    assert response.headers["set-cookie"].startswith(f"access_token={token}")


async def test_start_page_session_not_logged_in(client: AsyncClient):
    response = await client.post("/api/users/session")

    assert response.status_code == 401


async def test_logout_clears_cookie(client: AsyncClient, headers: dict):
    response = await client.post("/api/users/logout")

    assert response.status_code == 204
    assert 'access_token=""' in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert client.cookies.get("access_token") is None


async def test_login_rate_limit(client: AsyncClient, rate_limits_on):
    for _ in range(5):
        response = await client.post("/api/users/token", data={"username": "a@example.com", "password": "wrong"})
        assert response.status_code == 401

    response = await client.post("/api/users/token", data={"username": "a@example.com", "password": "wrong"})

    assert response.status_code == 429
    assert response.json()["detail"] == "Too many attempts. Please wait a while and try again."


async def test_forgot_password_rate_limit(client: AsyncClient, rate_limits_on):
    for _ in range(3):
        response = await client.post("/api/users/forgot-password", json={"email": "a@example.com"})
        assert response.status_code == 202

    response = await client.post("/api/users/forgot-password", json={"email": "a@example.com"})

    assert response.status_code == 429


async def test_reset_password_rate_limit(client: AsyncClient, rate_limits_on):
    body = {"token": "made-up", "new_password": "brandnewpassword"}
    for _ in range(5):
        response = await client.post("/api/users/reset-password", json=body)
        assert response.status_code == 400

    response = await client.post("/api/users/reset-password", json=body)

    assert response.status_code == 429


async def test_register_rate_limit(client: AsyncClient, rate_limits_on):
    for number in range(10):
        await create_test_user(client, username=f"user{number}", email=f"user{number}@example.com")

    response = await client.post(
        "/api/users", json={"username": "onemore", "email": "onemore@example.com", "password": "testpassword123"}
    )

    assert response.status_code == 429


async def test_delete_picture_s3_failure_still_succeeds(client: AsyncClient, headers: dict, mocked_aws):
    await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)
    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "DeleteObject")

    with patch("image_utils._delete_from_s3", side_effect=error):
        response = await client.delete("/api/users/me/picture", headers=headers)

    assert response.status_code == 200
    assert response.json()["image_file"] is None


async def test_delete_account_s3_failure_still_succeeds(client: AsyncClient, headers: dict, mocked_aws):
    await client.patch("/api/users/me/picture", files=upload(make_image_bytes()), headers=headers)
    error = ClientError({"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "DeleteObject")

    with patch("image_utils._delete_from_s3", side_effect=error):
        response = await client.delete("/api/users/me", headers=headers)

    assert response.status_code == 204
