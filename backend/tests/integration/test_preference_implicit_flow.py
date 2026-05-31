"""End-to-end: a tracking status change records an IMPLICIT preference signal.

Mirrors the harness in test_preference_flow.py:
- Real FastAPI app built in-process with dependency_overrides for auth and the
  tracking + preference service providers.
- Real SQLite in-memory DB (no Postgres required); the tracking and preference
  ORM tables use only JSON/UUID/String columns so they are sqlite-compatible.
- A fake vector store returns a controlled non-zero embedding for the tracked
  job so the implicit signal carries an embedding and the model activates.
- Both services share ONE InMemoryEventBus — exactly as the full app wires
  ``infra.event_bus`` — and the preference subscriber is registered on it the
  same way bootstrap.preference.build_preference does.
- The bus dispatches handlers via asyncio.create_task, so after the PATCH we
  poll a short loop yielding control until the implicit signal lands.
"""
from __future__ import annotations

import uuid as uuid_mod

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.adapters.event_bus import InMemoryEventBus
from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.ingestion.api.dependencies import get_ingestion_orchestrator
from hiresense.preference.api import router as preference_router
from hiresense.preference.api.dependencies import get_preference_service
from hiresense.preference.domain import (
    FeedbackKind,
    FeedbackSource,
    PreferenceService,
    TasteVectorCalculator,
    status_to_feedback_kind,
)
from hiresense.preference.infrastructure import PreferenceRepository
from hiresense.preference.infrastructure.orm import (  # noqa: F401  registers tables
    FeedbackSignalOrm,
    PreferenceModelOrm,
)
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.routes import router as tracking_router
from hiresense.tracking.domain import TrackingService
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.infrastructure import TrackingRepository
from hiresense.tracking.infrastructure.orm import (  # noqa: F401  registers tables
    TrackedApplicationOrm,
)

_DIM = 768
_NON_ZERO_EMBEDDING = [1.0] + [0.0] * (_DIM - 1)


class _FakeVectorStore:
    """Returns a controlled embedding for one specific job_id; None for all others."""

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


class _FakeOrchestrator:
    """The tracking routes enrich responses via get_job_by_id; None disables enrichment."""

    def get_job_by_id(self, job_id: str):  # noqa: ARG002
        return None


def _build_app(
    tracking_service: TrackingService,
    preference_service: PreferenceService,
) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_tracking_service] = lambda: tracking_service
    app.dependency_overrides[get_preference_service] = lambda: preference_service
    app.dependency_overrides[get_ingestion_orchestrator] = _FakeOrchestrator
    app.include_router(tracking_router)
    app.include_router(preference_router)
    return app


@pytest.mark.asyncio
async def test_status_change_records_implicit_signal() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    # One shared bus, exactly as infra.event_bus is shared in the real app.
    event_bus = InMemoryEventBus()

    job_id = uuid_mod.uuid4()
    vector_store = _FakeVectorStore()
    vector_store.seed(str(job_id), _NON_ZERO_EMBEDDING)

    preference_repo = PreferenceRepository(session_factory=session_factory)
    calculator = TasteVectorCalculator(alpha=0.5, beta=0.8, gamma=0.2, tau_days=30.0)
    weights = {kind: 1.0 for kind in FeedbackKind}
    preference_service = PreferenceService(
        repository=preference_repo,
        vector_store=vector_store,
        calculator=calculator,
        weights=weights,
        enabled=True,
    )

    # Register the subscriber the same way bootstrap.preference.build_preference does.
    async def _on_status_changed(event) -> None:
        kind = status_to_feedback_kind(event.status)
        if kind is None or event.job_id is None:
            return
        await preference_service.record_implicit_signal(uuid_mod.UUID(event.job_id), kind)

    event_bus.subscribe("tracking.status_changed", _on_status_changed)

    tracking_repo = TrackingRepository(session_factory=session_factory)
    tracking_service = TrackingService(
        repository=tracking_repo,
        ingestion_orchestrator=_FakeOrchestrator(),
        event_bus=event_bus,
    )

    # Seed a job-linked tracked application in SAVED state.
    created = tracking_repo.create(
        TrackedApplication(
            job_id=job_id,
            title="Senior Engineer",
            company="Acme",
            status=ApplicationStatus.SAVED.value,
        )
    )

    app = _build_app(tracking_service, preference_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No implicit signals yet.
        r = await client.get("/preference/signals")
        assert r.status_code == 200, r.text
        assert r.json() == []

        # Transition the tracked application to "offered".
        r = await client.patch(
            f"/tracking/{created.id}",
            json={"status": "offered"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "offered"

        # The bus dispatches the handler via asyncio.create_task — poll briefly,
        # yielding control so the scheduled task can run and persist the signal.
        signal_seen = False
        for _ in range(50):
            r = await client.get("/preference/signals")
            assert r.status_code == 200, r.text
            signals = r.json()
            if signals:
                signal_seen = True
                break

        assert signal_seen, "implicit signal was never recorded"
        assert len(signals) == 1
        assert signals[0]["job_id"] == str(job_id)
        assert signals[0]["kind"] == "offered"

        # The /preference/signals response schema does not expose `source`, so
        # assert the IMPLICIT source by querying the preference repo directly.
        persisted = preference_repo.list_signals()
        assert len(persisted) == 1
        assert persisted[0].source == FeedbackSource.IMPLICIT
        assert persisted[0].kind == FeedbackKind.OFFERED
        assert persisted[0].job_id == job_id

        # Explain reflects the implicit positive signal.
        r = await client.get("/preference/explain")
        assert r.status_code == 200, r.text
        explain = r.json()
        assert explain["total_signals"] >= 1
        assert explain["positive_count"] >= 1

    Base.metadata.drop_all(engine)
