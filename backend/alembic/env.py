import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

import hiresense.infrastructure.registry  # noqa: F401 — registers all ORM models
from hiresense.infrastructure.database import Base

# Load backend/.env before anything reads os.environ, so migrations honor the
# same config as the running app: the migration target (DATABASE_URL below) and
# the pgvector column dimension (the raw-SQL vector migrations size their column
# from os.environ["EMBEDDING_DIM"]). Without this, `alembic upgrade` silently
# targeted alembic.ini's URL and defaulted the vector dimension to 768.
load_dotenv()

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL (env or .env) is the single source of truth for the migration
# target, matching hiresense.config. alembic.ini ships without credentials; its
# `sqlalchemy.url` is only a fallback for tooling that sets it explicitly. The
# app strips `+asyncpg` for its sync engine (see bootstrap.shared_infra), but
# Alembic runs its own async engine here, so the async URL is used as-is.
_database_url = os.environ.get("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
if not _database_url:
    raise RuntimeError(
        "DATABASE_URL is not set. Export it (or set it in backend/.env) before "
        "running Alembic — migrations need a Postgres target (pgvector has no "
        "SQLite fallback)."
    )
config.set_main_option("sqlalchemy.url", _database_url)

target_metadata = Base.metadata


def _include_object(object_, name, type_, reflected, compare_to) -> bool:
    """Exclude the pgvector-managed `vector_embeddings` table from autogenerate.

    It is created and owned by the raw-SQL migration 014 (the pgvector `vector`
    column type has no ORM model and isn't reflectable), so without this filter
    `alembic check` reports it — and its index — as spurious drift against a
    freshly-migrated database.
    """
    if type_ == "table" and name == "vector_embeddings":
        return False
    parent = getattr(object_, "table", None)
    if type_ == "index" and parent is not None and parent.name == "vector_embeddings":
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
