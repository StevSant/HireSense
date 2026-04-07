from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from hiresense.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings):
    return create_async_engine(settings.database_url, echo=settings.debug)


def build_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    engine = build_engine(settings)
    return async_sessionmaker(engine, expire_on_commit=False)


# Import models so Base.metadata registers them for Alembic autogenerate
from hiresense.tracking.domain.models import TrackedApplication  # noqa: E402, F401
