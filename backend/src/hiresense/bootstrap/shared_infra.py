from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.adapters.event_bus import InMemoryEventBus
from hiresense.adapters.http import RetryingAsyncClient
from hiresense.config import Settings


@dataclass(frozen=True)
class SharedInfra:
    """Cross-cutting infrastructure shared by every module builder."""

    settings: Settings
    # A RetryingAsyncClient wrapping the raw httpx.AsyncClient — a drop-in for
    # the verbs the adapters use (get/post/request) plus pass-through for the
    # rest. Typed loosely because the wrapper is not an AsyncClient subclass.
    http_client: Any
    event_bus: InMemoryEventBus
    sync_session_factory: Any
    embedding: Any
    vector_store: Any
    # In-process CompanyProfileStore: ingestion adapters record source-provided
    # company profiles here, the research service reads them to ground its
    # prompt. Shared cross-module state, like the event bus and caches.
    company_profile_store: Any


def build_shared_infra(settings: Settings, http_client: httpx.AsyncClient) -> SharedInfra:
    from hiresense.research.domain import CompanyProfileStore

    event_bus = InMemoryEventBus()
    company_profile_store = CompanyProfileStore()

    # Wrap the raw client with retry/backoff so transient transport errors and
    # retryable status codes no longer abort an entire source fetch. The raw
    # client is still what main.py owns and aclose()s on shutdown.
    retrying_http_client = RetryingAsyncClient(
        http_client,
        max_retries=settings.http_max_retries,
        base_delay=settings.http_retry_base_delay,
        retry_status_codes=settings.http_retry_status_codes,
    )

    sync_db_url = settings.database_url.replace("+asyncpg", "")
    # SQLite (tests) has no server-side pool semantics — pool kwargs would be
    # rejected or meaningless there.
    pool_kwargs = (
        {}
        if sync_db_url.startswith("sqlite")
        else {
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_pre_ping": settings.db_pool_pre_ping,
            "pool_recycle": settings.db_pool_recycle_seconds,
        }
    )
    sync_engine = create_engine(sync_db_url, echo=settings.debug, **pool_kwargs)
    sync_session_factory = sessionmaker(bind=sync_engine, expire_on_commit=False)

    # Imported lazily so the heavy sentence-transformers model is only loaded
    # when an app is actually built (not at module-collection time).
    from hiresense.adapters.embedding import SentenceTransformerAdapter

    embedding = SentenceTransformerAdapter(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
    )

    vector_store = None
    if settings.vector_store_provider == "pgvector":
        from hiresense.adapters.vector_store import PgVectorStore

        vector_store = PgVectorStore(sync_session_factory, dim=settings.embedding_dim)

    return SharedInfra(
        settings=settings,
        http_client=retrying_http_client,
        event_bus=event_bus,
        sync_session_factory=sync_session_factory,
        embedding=embedding,
        vector_store=vector_store,
        company_profile_store=company_profile_store,
    )
