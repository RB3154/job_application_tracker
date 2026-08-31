"""PostgreSQL database configuration for the application."""

from collections.abc import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Settings(BaseSettings):
    """Application settings loaded from the project .env file."""

    database_url: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def _psycopg_database_url(database_url: str) -> URL:
    """Return a PostgreSQL URL configured to use SQLAlchemy's psycopg driver."""

    url = make_url(database_url)
    if url.drivername not in {"postgresql", "postgres", "postgresql+psycopg"}:
        raise ValueError("DATABASE_URL must use a PostgreSQL URL.")

    return url.set(drivername="postgresql+psycopg")


settings = Settings()
engine = create_engine(_psycopg_database_url(settings.database_url))
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for the project's SQLAlchemy ORM models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for use as a FastAPI dependency."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
