from io import BytesIO
from unittest.mock import AsyncMock, patch

import aiosmtplib
import pytest
from PIL import Image, UnidentifiedImageError

import models
from auth import (
    create_user_access_token,
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_access_token,
    verify_password,
)
from config import settings
from database import _async_postgresql_database_url
from email_utils import send_password_reset_email
from image_utils import process_profile_image
from routers.helpers import contains_pattern, slugify
from schemas import check_web_address
from tests.conftest import make_image_bytes


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Google India", "google-india"),
        ("  Spaces  around ", "spaces-around"),
        ("C++ / Rust!", "c-rust"),
        ("Café Münster", "cafe-munster"),
        ("!!!", ""),
    ],
)
def test_slugify(text: str, expected: str):
    assert slugify(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("python", "%python%"),
        ("100%", "%100\\%%"),
        ("a_b", "%a\\_b%"),
        ("a\\b", "%a\\\\b%"),
    ],
)
def test_contains_pattern(text: str, expected: str):
    assert contains_pattern(text) == expected


@pytest.mark.parametrize("url", ["https://example.com", "http://example.com/a?b=1", "HTTPS://EXAMPLE.COM"])
def test_check_web_address_accepts(url: str):
    assert check_web_address(url) == url


@pytest.mark.parametrize("url", ["example.com", "ftp://example.com", "javascript:alert(1)", "https://", ""])
def test_check_web_address_rejects(url: str):
    with pytest.raises(ValueError):
        check_web_address(url)


@pytest.mark.parametrize(
    "url",
    ["postgresql://u:p@localhost/db", "postgres://u:p@localhost/db", "postgresql+psycopg://u:p@localhost/db"],
)
def test_database_url_switches_to_asyncpg(url: str):
    assert _async_postgresql_database_url(url).drivername == "postgresql+asyncpg"


def test_database_url_must_be_postgresql():
    with pytest.raises(ValueError):
        _async_postgresql_database_url("sqlite:///test.db")


def test_password_hash_and_verify():
    hashed = hash_password("my-password")

    assert hashed != "my-password"
    assert verify_password("my-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_same_password_hashes_differently_each_time():
    assert hash_password("my-password") != hash_password("my-password")


def test_reset_tokens_are_random():
    assert generate_reset_token() != generate_reset_token()


def test_reset_token_hash_is_repeatable():
    assert hash_reset_token("abc") == hash_reset_token("abc")
    assert hash_reset_token("abc") != hash_reset_token("abd")
    assert len(hash_reset_token("abc")) == 64


def test_access_token_contains_user_and_version():
    user = models.User(id=7, token_version=3)

    claims = verify_access_token(create_user_access_token(user))

    assert claims["sub"] == "7"
    assert claims["ver"] == 3


def test_verify_access_token_rejects_garbage():
    assert verify_access_token("not-a-token") is None


def test_image_path_is_none_without_a_picture():
    assert models.User(image_file=None).image_path is None


def test_image_path_points_at_s3():
    path = models.User(image_file="abc.jpg").image_path

    assert path == f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/profile_pics/abc.jpg"


@pytest.mark.parametrize(
    ("image_format", "mode"),
    [("JPEG", "RGB"), ("PNG", "RGBA"), ("PNG", "P"), ("GIF", "P"), ("WEBP", "RGB")],
)
def test_process_image_makes_300px_square_jpeg(image_format: str, mode: str):
    processed, filename = process_profile_image(make_image_bytes(image_format, size=(640, 200), mode=mode))

    assert filename.endswith(".jpg")
    with Image.open(BytesIO(processed)) as result:
        assert result.format == "JPEG"
        assert result.mode == "RGB"
        assert result.size == (300, 300)


def test_process_image_gives_each_picture_a_new_name():
    image = make_image_bytes()

    assert process_profile_image(image)[1] != process_profile_image(image)[1]


def test_process_image_applies_phone_rotation():
    original = Image.new("RGB", (400, 400), "blue")
    original.paste("red", (0, 0, 200, 400))
    exif = Image.Exif()
    exif[0x0112] = 6
    output = BytesIO()
    original.save(output, "PNG", exif=exif)

    processed, _ = process_profile_image(output.getvalue())

    with Image.open(BytesIO(processed)) as result:
        top_red = result.getpixel((150, 30))[0]
        bottom_red = result.getpixel((150, 270))[0]
    assert top_red > 200
    assert bottom_red < 50


def test_process_image_rejects_non_images():
    with pytest.raises(UnidentifiedImageError):
        process_profile_image(b"not an image")


@pytest.mark.anyio
async def test_reset_email_contains_the_link():
    with patch("email_utils.aiosmtplib.send", new_callable=AsyncMock) as mock_smtp:
        await send_password_reset_email(to_email="me@example.com", username="rudra", token="abc123")

    mock_smtp.assert_awaited_once()
    message = mock_smtp.call_args.args[0]
    assert message["To"] == "me@example.com"
    assert message["From"] == settings.mail_from
    assert message["Subject"] == "Reset Your Password - Job Application Tracker"
    body = message.get_content()
    assert "Hi rudra," in body
    assert f"{settings.frontend_url}/reset-password?token=abc123" in body


@pytest.mark.anyio
@pytest.mark.parametrize("error", [aiosmtplib.SMTPException("refused"), OSError("no network")])
async def test_reset_email_failure_is_logged_without_the_token(error: Exception, caplog: pytest.LogCaptureFixture):
    with patch("email_utils.aiosmtplib.send", new_callable=AsyncMock, side_effect=error):
        await send_password_reset_email(to_email="me@example.com", username="rudra", token="secret-token")

    assert "Could not send the password reset email" in caplog.text
    assert "secret-token" not in caplog.text
