import os
from collections.abc import AsyncGenerator
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, patch

from dotenv import dotenv_values
from sqlalchemy.engine import make_url


_project_url = os.environ.get("TEST_DATABASE_URL")
if _project_url is None:
    _real_url = make_url(dotenv_values(Path(__file__).parent.parent / ".env")["DATABASE_URL"])
    _project_url = _real_url.set(database=f"{_real_url.database}_test").render_as_string(hide_password=False)
os.environ["DATABASE_URL"] = _project_url

os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-not-a-real-one"

os.environ["S3_BUCKET_NAME"] = "test-bucket"
os.environ["S3_REGION"] = "us-east-1"
os.environ["S3_ACCESS_KEY_ID"] = "testing"
os.environ["S3_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ.pop("S3_ENDPOINT_URL", None)

os.environ["MAIL_SERVER"] = "localhost"
os.environ["MAIL_USERNAME"] = ""
os.environ["MAIL_PASSWORD"] = ""

import boto3
import pytest
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import settings
from database import Base, _async_postgresql_database_url, get_db
from main import app
from rate_limit import limiter


_test_database_url = _async_postgresql_database_url(settings.database_url)
if not (_test_database_url.database or "").endswith("_test"):
    raise RuntimeError(f"Refusing to run tests: database {_test_database_url.database!r} doesn't end in '_test'.")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def test_engine():
    return create_async_engine(_test_database_url, poolclass=NullPool)


@pytest.fixture(scope="session")
async def setup_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest.fixture
async def db_session(test_engine, setup_database) -> AsyncGenerator[AsyncSession]:
    conn = await test_engine.connect()
    trans = await conn.begin()

    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    async with test_async_session() as session:
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
            await conn.close()


@pytest.fixture
def mocked_aws():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=os.environ["S3_BUCKET_NAME"])
        yield s3


@pytest.fixture(autouse=True)
def mock_send_email():
    with patch("routers.users.send_password_reset_email", new_callable=AsyncMock) as mock_send:
        yield mock_send


@pytest.fixture(autouse=True)
def no_rate_limits():
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def rate_limits_on(no_rate_limits):
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def headers(client: AsyncClient) -> dict[str, str]:
    await create_test_user(client)
    return auth_header(await login_user(client))


@pytest.fixture
async def other_headers(client: AsyncClient) -> dict[str, str]:
    await create_test_user(client, username="otheruser", email="other@example.com")
    return auth_header(await login_user(client, email="other@example.com"))


async def create_test_user(
    client: AsyncClient,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> dict:
    response = await client.post("/api/users", json={"username": username, "email": email, "password": password})
    assert response.status_code == 201, f"Failed to create user: {response.text}"
    return response.json()


async def login_user(client: AsyncClient, email: str = "test@example.com", password: str = "testpassword123") -> str:
    response = await client.post("/api/users/token", data={"username": email, "password": password})
    assert response.status_code == 200, f"Failed to login: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def create_company(client: AsyncClient, headers: dict, name: str = "Acme Corp", **fields) -> dict:
    response = await client.post("/api/companies", json={"company_name": name, **fields}, headers=headers)
    assert response.status_code == 201, f"Failed to create company: {response.text}"
    return response.json()


def job_payload(company_id: str, **fields) -> dict:
    return {
        "role": "Backend Engineer",
        "job_url": "https://careers.example.com/1",
        "job_posting_date": "2026-01-15",
        "company_id": company_id,
        **fields,
    }


async def create_job(client: AsyncClient, headers: dict, company_id: str | None = None, **fields) -> dict:
    if company_id is None:
        company_id = (await create_company(client, headers))["company_id"]
    response = await client.post("/api/jobs", json=job_payload(company_id, **fields), headers=headers)
    assert response.status_code == 201, f"Failed to create job: {response.text}"
    return response.json()


async def create_application(client: AsyncClient, headers: dict, job_id: str | None = None, **fields) -> dict:
    if job_id is None:
        job_id = (await create_job(client, headers))["job_id"]
    response = await client.post("/api/applications", json={"job_id": job_id, **fields}, headers=headers)
    assert response.status_code == 201, f"Failed to create application: {response.text}"
    return response.json()


async def create_lookup(client: AsyncClient, headers: dict, path: str, name: str) -> dict:
    response = await client.post(path, json={"name": name}, headers=headers)
    assert response.status_code == 201, f"Failed to create lookup entry: {response.text}"
    return response.json()


def make_image_bytes(image_format: str = "JPEG", size: tuple[int, int] = (500, 400), mode: str = "RGB") -> bytes:
    output = BytesIO()
    Image.new(mode, size).save(output, image_format)
    return output.getvalue()
