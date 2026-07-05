from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Database connection + pooling and vector-store provider selection."""

    # Database. Required in BOTH modes (pgvector ANN needs Postgres; no SQLite
    # fallback) — enforced by config.mode.apply_mode, hence the empty default here.
    database_url: str = ""
    # Connection-pool sizing for the shared sync engine. pool_size persistent
    # connections + up to max_overflow burst ones; pre_ping validates a
    # connection before reuse (drops stale ones after DB restarts); recycle
    # replaces connections older than this many seconds.
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_pool_recycle_seconds: int = 3600

    # Vector Store
    vector_store_provider: str = "pgvector"
