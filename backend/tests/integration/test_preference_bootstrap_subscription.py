"""Coverage for the REAL ``build_preference`` event-bus subscription.

The sibling test ``test_preference_implicit_flow.py`` inlines its own copy of
the bus subscriber, so a regression that drops or breaks the
``infra.event_bus.subscribe("tracking.status_changed", ...)`` call inside
``bootstrap.preference.build_preference`` would pass silently there. This test
closes that gap: it constructs a real :class:`SharedInfra`, calls the real
``build_preference(infra)`` (the code under test — its own ``subscribe()`` is
what registers the handler), then publishes events through the real
:class:`InMemoryEventBus` and asserts the persisted signals.

The bus dispatches handlers via ``asyncio.create_task``, so after publishing we
``await asyncio.sleep(0)`` in a short poll loop to let the scheduled task run.
"""
from __future__ import annotations

import asyncio
import uuid as uuid_mod

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.adapters.event_bus import InMemoryEventBus
from hiresense.bootstrap.preference import build_preference
from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.config import Settings
from hiresense.infrastructure.database import Base
from hiresense.kernel.events import TrackingStatusChangedEvent
from hiresense.preference.domain import FeedbackKind, FeedbackSource
from hiresense.preference.infrastructure.orm import (  # noqa: F401  registers tables
    FeedbackSignalOrm,
    PreferenceModelOrm,
)

_DIM = 768
_NON_ZERO_EMBEDDING = [1.0] + [0.0] * (_DIM - 1)


class _FakeVectorStore:
    """Returns a controlled embedding for one specific job_id; None otherwise."""

    def __init__(self) -> None:
        self._embeddings: dict[str, list[float]] = {}

    def seed(self, job_id: str, embedding: list[float]) -> None:
        self._embeddings[job_id] = embedding

    async def get_vector(self, id: str) -> list[float] | None:
        return self._embeddings.get(id)

    async def upsert(self, id, embedding, metadata) -> None:  # noqa: ARG002
        pass

    async def search(self, query_embedding, *, top_k=10, filters=None):  # noqa: ARG002
        return []

    async def delete(self, ids) -> None:  # noqa: ARG002
        pass


async def _wait_for(predicate, *, tries: int = 50) -> bool:
    """Yield control repeatedly so create_task-dispatched handlers can run."""
    for _ in range(tries):
        if predicate():
            return True
        await asyncio.sleep(0)
    return predicate()


@pytest.mark.asyncio
async def test_build_preference_subscribes_to_status_changed() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    job_id = uuid_mod.uuid4()
    vector_store = _FakeVectorStore()
    vector_store.seed(str(job_id), _NON_ZERO_EMBEDDING)

    event_bus = InMemoryEventBus()

    # build_preference only reads settings, sync_session_factory, vector_store
    # and event_bus off infra — http_client and embedding are unused here, so
    # pass None for them rather than loading the heavy embedding model.
    infra = SharedInfra(
        settings=Settings(),
        http_client=None,
        event_bus=event_bus,
        sync_session_factory=session_factory,
        embedding=None,
        vector_store=vector_store,
    )

    # Code under test: build_preference must perform the real subscribe().
    build = build_preference(infra)

    try:
        # No signals before any event.
        assert build.service.list_signals() == []

        # A mappable, job-linked status change records ONE implicit signal.
        await event_bus.publish(
            TrackingStatusChangedEvent(job_id=str(job_id), status="offered")
        )
        assert await _wait_for(lambda: len(build.service.list_signals()) >= 1), (
            "implicit signal was never recorded — build_preference may not have "
            "subscribed to tracking.status_changed"
        )

        signals = build.service.list_signals()
        assert len(signals) == 1
        assert signals[0].job_id == job_id
        assert signals[0].kind == FeedbackKind.OFFERED
        assert signals[0].source == FeedbackSource.IMPLICIT

        # No-op path: job_id=None is ignored, and "saved" maps to no kind.
        await event_bus.publish(
            TrackingStatusChangedEvent(job_id=None, status="offered")
        )
        await event_bus.publish(
            TrackingStatusChangedEvent(job_id=str(job_id), status="saved")
        )
        # Give any (erroneously) scheduled handlers a chance to run, then assert
        # no additional signal was recorded.
        for _ in range(10):
            await asyncio.sleep(0)
        assert len(build.service.list_signals()) == 1
    finally:
        Base.metadata.drop_all(engine)
