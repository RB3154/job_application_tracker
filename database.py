from collections.abc import AsyncGenerator

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings


def _async_postgresql_database_url(database_url: str) -> URL:
    url = make_url(database_url)
    if url.drivername not in {
        "postgresql",
        "postgres",
        "postgresql+asyncpg",
        "postgresql+psycopg",
    }:
        raise ValueError("DATABASE_URL must use a PostgreSQL URL.")

    return url.set(drivername="postgresql+asyncpg")


engine = create_async_engine(_async_postgresql_database_url(settings.database_url), pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        yield db
