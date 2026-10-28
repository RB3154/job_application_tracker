"""Tests for the profile picture endpoints: PATCH and DELETE /api/users/me/picture.

Each test that uploads a picture makes its own user and deletes them at the end,
so their picture files on disk are cleaned up too.
"""

from io import BytesIO

import pytest
from PIL import Image

from conftest import make_user
from config import settings
from image import PROFILE_PICS_DIR


def image_bytes(image_format: str = "PNG", mode: str = "RGB", size: tuple[int, int] = (500, 400)) -> bytes:
    """Make a small image in memory (no real file needed) to upload as a profile picture."""

    buffer = BytesIO()
    Image.new(mode, size, "red").save(buffer, image_format)
    return buffer.getvalue()


def upload(client, headers, content: bytes, filename: str = "me.png", content_type: str = "image/png"):
    """Send a picture upload, the same as choosing a file in Swagger."""

    files = {"file": (filename, content, content_type)}
    return client.patch("/api/users/me/picture", files=files, headers=headers)


@pytest.fixture
def pic_user(client):
    """A fresh logged-in user for one test. Deleted afterwards, along with their picture."""

    user, headers = make_user(client, "pic")
    yield user, headers
    client.delete("/api/users/me", headers=headers)


# --- Upload: PATCH /api/users/me/picture ---


# Uploading a picture saves it as a 300x300 JPEG and the profile points to it.
def test_upload_saves_300x300_jpeg(client, pic_user):
    _, headers = pic_user
    response = upload(client, headers, image_bytes())
    assert response.status_code == 200, response.text

    filename = response.json()["image_file"]
    assert filename.endswith(".jpg")
    assert response.json()["image_path"] == f"/media/profile_pics/{filename}"
    with Image.open(PROFILE_PICS_DIR / filename) as saved:
        assert saved.size == (300, 300)
        assert saved.format == "JPEG"


# The uploaded picture can be opened in the browser through its image_path.
def test_uploaded_picture_is_served(client, pic_user):
    _, headers = pic_user
    image_path = upload(client, headers, image_bytes()).json()["image_path"]

    response = client.get(image_path)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


# After uploading, the picture shows on /me and on the public profile.
def test_picture_shows_on_profiles(client, pic_user):
    user, headers = pic_user
    filename = upload(client, headers, image_bytes()).json()["image_file"]

    assert client.get("/api/users/me", headers=headers).json()["image_file"] == filename
    assert client.get(f"/api/users/{user['id']}").json()["image_file"] == filename


# Other image types work too. A transparent PNG (RGBA) is turned into a JPEG,
# which has no transparency.
@pytest.mark.parametrize(
    ("image_format", "mode", "content_type"),
    [
        ("JPEG", "RGB", "image/jpeg"),
        ("PNG", "RGBA", "image/png"),
        ("GIF", "P", "image/gif"),
        ("WEBP", "RGB", "image/webp"),
    ],
)
def test_upload_accepts_other_image_types(client, pic_user, image_format, mode, content_type):
    _, headers = pic_user
    response = upload(client, headers, image_bytes(image_format, mode), f"me.{image_format.lower()}", content_type)
    assert response.status_code == 200, response.text
    with Image.open(PROFILE_PICS_DIR / response.json()["image_file"]) as saved:
        assert saved.format == "JPEG"
        assert saved.mode == "RGB"


# A small or oddly shaped image is still cropped/stretched to exactly 300x300.
def test_upload_small_image_becomes_300x300(client, pic_user):
    _, headers = pic_user
    filename = upload(client, headers, image_bytes(size=(50, 120))).json()["image_file"]
    with Image.open(PROFILE_PICS_DIR / filename) as saved:
        assert saved.size == (300, 300)


# Uploading again replaces the picture, and the old file is removed from disk.
def test_upload_replaces_old_picture(client, pic_user):
    _, headers = pic_user
    first = upload(client, headers, image_bytes()).json()["image_file"]
    second = upload(client, headers, image_bytes()).json()["image_file"]

    assert second != first
    assert not (PROFILE_PICS_DIR / first).exists()
    assert (PROFILE_PICS_DIR / second).exists()


# A file that isn't an image is refused with 400, and the profile is unchanged.
def test_upload_non_image_is_rejected(client, pic_user):
    _, headers = pic_user
    response = upload(client, headers, b"just some text", "notes.txt", "text/plain")
    assert response.status_code == 400
    assert client.get("/api/users/me", headers=headers).json()["image_file"] is None


# A file bigger than the size limit (5 MB by default) is refused with 400.
def test_upload_too_large_is_rejected(client, pic_user):
    _, headers = pic_user
    too_big = b"0" * (settings.max_upload_size_bytes + 1)
    response = upload(client, headers, too_big)
    assert response.status_code == 400
    assert "too large" in response.json()["detail"]


# Sending the request without a file is a validation error (422).
def test_upload_without_file_is_422(client, pic_user):
    _, headers = pic_user
    assert client.patch("/api/users/me/picture", headers=headers).status_code == 422


# Uploading without logging in is refused with 401.
def test_upload_requires_login(client):
    assert upload(client, {}, image_bytes()).status_code == 401


# --- Delete: DELETE /api/users/me/picture ---


# Deleting your picture clears it from the profile and removes the file.
def test_delete_picture(client, pic_user):
    _, headers = pic_user
    filename = upload(client, headers, image_bytes()).json()["image_file"]

    response = client.delete("/api/users/me/picture", headers=headers)
    assert response.status_code == 200
    assert response.json()["image_file"] is None
    assert response.json()["image_path"] is None
    assert not (PROFILE_PICS_DIR / filename).exists()


# Deleting when there's no picture gives 400.
def test_delete_picture_when_none_is_400(client, pic_user):
    _, headers = pic_user
    assert client.delete("/api/users/me/picture", headers=headers).status_code == 400


# Deleting a picture without logging in is refused with 401.
def test_delete_picture_requires_login(client):
    assert client.delete("/api/users/me/picture").status_code == 401


# --- Deleting the account ---


# Deleting your account also deletes your picture file.
def test_delete_account_removes_picture(client):
    _, headers = make_user(client, "pic")
    filename = upload(client, headers, image_bytes()).json()["image_file"]

    assert client.delete("/api/users/me", headers=headers).status_code == 204
    assert not (PROFILE_PICS_DIR / filename).exists()
