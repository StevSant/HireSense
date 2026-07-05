"""End-to-end: feedback changes the taste vector, reset restores baseline.

Mirrors the harness established in test_ingestion_to_api_flow.py:
- Real FastAPI app built in-process with dependency_overrides for auth and
  the preference service provider.
- Real SQLite in-memory DB (no Postgres required) — the preference ORM tables
  use only JSON/UUID/String columns so they are fully sqlite-compatible.
- A fake vector store returns a controlled non-zero embedding so the delta
  vector becomes non-zero and the model transitions to active=True.
- Auth is satisfied by overriding require_auth to return a fixed subject
  string, exactly as allowed by FastAPI's dependency_overrides mechanism.
"""

from __future__ import annotations

import uuid as uuid_mod

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.infrastructure.database import Base
from hiresense.identity.api.dependencies import require_auth
from hiresense.preference.api import router
from hiresense.preference.api.dependencies import get_preference_service
from hiresense.preference.domain import (
    FeedbackKind,
    PreferenceService,
    TasteVectorCalculator,
)
from hiresense.preference.infrastructure import PreferenceRepository
from hiresense.preference.infrastructure.orm import (  # noqa: F401  registers tables
    FeedbackSignalOrm,
    PreferenceModelOrm,
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


def _build_app(service: PreferenceService) -> FastAPI:
    app = FastAPI()
    # Override auth: no JWT validation needed in tests — just return a fixed subject.
    app.dependency_overrides[require_auth] = lambda: "test-user"
    # Override the service provider so it uses our in-memory-backed instance.
    app.dependency_overrides[get_preference_service] = lambda: service
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_feedback_builds_then_reset_clears_model() -> None:
    # --- infrastructure setup (mirrors test_ingestion_to_api_flow.py) ---
    # StaticPool forces a single shared connection so that tables created in the
    # main thread are visible to SQLAlchemy sessions opened from threadpool
    # workers (FastAPI runs sync route handlers via anyio.to_thread.run_sync).
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    vector_store = _FakeVectorStore()
    job_id = uuid_mod.uuid4()
    vector_store.seed(str(job_id), _NON_ZERO_EMBEDDING)

    repo = PreferenceRepository(session_factory=session_factory)
    calculator = TasteVectorCalculator(alpha=0.5, beta=0.8, gamma=0.2, tau_days=30.0)
    weights = {kind: 1.0 for kind in FeedbackKind}
    service = PreferenceService(
        repository=repo,
        vector_store=vector_store,
        calculator=calculator,
        weights=weights,
        enabled=True,
    )

    app = _build_app(service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. No signals yet → explain reports active: False
        r = await client.get("/preference/explain")
        assert r.status_code == 200, r.text
        assert r.json()["active"] is False

        # 2. Submit a thumbs_up signal for a job with a non-zero indexed embedding
        r = await client.post(
            "/preference/feedback",
            json={"job_id": str(job_id), "kind": "thumbs_up"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["job_id"] == str(job_id)
        assert body["kind"] == "thumbs_up"

        # 3. Signals list contains exactly one entry
        r = await client.get("/preference/signals")
        assert r.status_code == 200, r.text
        signals = r.json()
        assert len(signals) == 1
        assert signals[0]["job_id"] == str(job_id)

        # 4. Explain now reports active: True with positive_count == 1
        r = await client.get("/preference/explain")
        assert r.status_code == 200, r.text
        explain = r.json()
        assert explain["active"] is True
        assert explain["positive_count"] == 1
        assert explain["total_signals"] == 1

        # 5. Reset clears all signals and deactivates the model
        r = await client.post("/preference/reset")
        assert r.status_code == 204, r.text

        r = await client.get("/preference/signals")
        assert r.status_code == 200, r.text
        assert r.json() == []

        r = await client.get("/preference/explain")
        assert r.status_code == 200, r.text
        assert r.json()["active"] is False

    Base.metadata.drop_all(engine)
