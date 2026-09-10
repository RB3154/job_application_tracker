"""PostgreSQL database configuration for the application."""

from collections.abc import AsyncGenerator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Settings(BaseSettings):
    """Application settings loaded from the project .env file."""

    database_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def _async_postgresql_database_url(database_url: str) -> URL:
    """Return a PostgreSQL URL configured for SQLAlchemy's asyncpg driver."""

    url = make_url(database_url)
    if url.drivername not in {
        "postgresql",
        "postgres",
        "postgresql+asyncpg",
        "postgresql+psycopg",
    }:
        raise ValueError("DATABASE_URL must use a PostgreSQL URL.")

    return url.set(drivername="postgresql+asyncpg")


settings = Settings()
engine = create_async_engine(_async_postgresql_database_url(settings.database_url))
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for the project's SQLAlchemy ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for use as a FastAPI dependency."""

    async with AsyncSessionLocal() as db:
        yield db
