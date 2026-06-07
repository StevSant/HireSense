"""Integration: Phase 2 dimension-weight nudging end to end.

Builds a real FastAPI app over an in-memory SQLite DB (no Postgres), wires the
preference service exactly as bootstrap does (nudge calculator + a fake
dimension-score lookup standing in for cached match scoring), and verifies:

- below the gate, /preference/weights shows zero overrides and a matching
  composite equals the base-weight composite (backward compatible);
- once enough outcome signals exist, an override appears on /weights and the
  same MatchingOrchestrator (sharing the preference port) produces a shifted
  composite;
- POST /preference/reset clears both the taste delta and the weight overrides.
"""
from __future__ import annotations

import uuid as uuid_mod

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.services import MatchingOrchestrator
from hiresense.preference.api import router as preference_router
from hiresense.preference.api.dependencies import get_preference_service
from hiresense.preference.domain import (
    FeedbackKind,
    PreferenceService,
    TasteVectorCalculator,
    WeightNudgeCalculator,
)
from hiresense.preference.infrastructure import PreferenceRepository
from hiresense.preference.infrastructure.orm import (  # noqa: F401  registers tables
    FeedbackSignalOrm,
    PreferenceModelOrm,
)

_BASE_COMP_WEIGHT = 10
_BASE_CULTURE_WEIGHT = 10


class _FakeVectorStore:
    async def get_vector(self, id: str) -> list[float] | None:  # noqa: ARG002
        return None  # no embedding needed for the weight-nudge path


class _FakeDimLookup:
    """compensation always scored 1.0 on the outcome jobs -> positive nudge."""

    def get_dimension_scores(self, job_id: str):  # noqa: ARG002
        return {"compensation": 1.0, "culture_fit": 0.5}


class _FakeScorer:
    def __init__(self, dimension, score, weight):
        self._dimension, self._score, self._weight = dimension, score, weight

    @property
    def dimension_name(self):
        return self._dimension

    @property
    def weight(self):
        return self._weight

    async def score(self, job, profile=None):  # noqa: ARG002
        return DimensionResult(
            dimension=self._dimension, score=self._score, rationale="", weight=self._weight
        )


class _FakeEventBus:
    async def publish(self, event):  # noqa: ARG002
        pass


def _build_service(session_factory) -> PreferenceService:
    return PreferenceService(
        repository=PreferenceRepository(session_factory=session_factory),
        vector_store=_FakeVectorStore(),
        calculator=TasteVectorCalculator(alpha=1.0, beta=1.0, gamma=1.0, tau_days=90.0),
        weights={k: 1.0 for k in FeedbackKind},
        enabled=True,
        nudge_calculator=WeightNudgeCalculator(min_outcomes=3, clamp=3, scale=10.0),
        base_weights={
            "compensation": _BASE_COMP_WEIGHT,
            "culture_fit": _BASE_CULTURE_WEIGHT,
        },
    )


def _build_app(service: PreferenceService) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_preference_service] = lambda: service
    app.include_router(preference_router)
    return app


async def _composite(orchestrator: MatchingOrchestrator) -> float:
    scorers = [
        _FakeScorer("compensation", 1.0, _BASE_COMP_WEIGHT),
        _FakeScorer("culture_fit", 0.0, _BASE_CULTURE_WEIGHT),
    ]
    result = await orchestrator.evaluate(
        job={"title": "SWE", "company": "Acme", "description": ""},
        dimension_scorers=scorers,
    )
    return result.composite_score


@pytest.mark.asyncio
async def test_weight_nudge_flow() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    service = _build_service(session_factory)
    service.attach_dimension_lookup(_FakeDimLookup())

    # A matching orchestrator sharing the same preference port (as in the app).
    orchestrator = MatchingOrchestrator(
        llm=None, event_bus=_FakeEventBus(), preference=service
    )

    app = _build_app(service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # --- Below the gate: no overrides, composite == base-weight composite ---
        r = await client.get("/preference/weights")
        assert r.status_code == 200, r.text
        rows = {row["dimension"]: row for row in r.json()}
        assert rows["compensation"]["override"] == 0
        assert rows["compensation"]["effective_weight"] == _BASE_COMP_WEIGHT

        base_composite = await _composite(orchestrator)
        # 1.0*10 + 0.0*10 = 10 / 20 = 0.5
        assert abs(base_composite - 0.5) < 1e-9

        # --- Cross the gate with 3 implicit OFFERED outcomes ---
        for _ in range(3):
            await service.record_implicit_signal(uuid_mod.uuid4(), FeedbackKind.OFFERED)

        r = await client.get("/preference/weights")
        rows = {row["dimension"]: row for row in r.json()}
        assert rows["compensation"]["override"] > 0
        boosted_weight = rows["compensation"]["effective_weight"]
        assert boosted_weight > _BASE_COMP_WEIGHT

        # The composite now weights compensation more heavily -> rises above 0.5.
        nudged_composite = await _composite(orchestrator)
        expected = (1.0 * boosted_weight + 0.0 * _BASE_CULTURE_WEIGHT) / (
            boosted_weight + _BASE_CULTURE_WEIGHT
        )
        # Composite is rounded to 4 dp by the orchestrator.
        assert abs(nudged_composite - expected) < 1e-4
        assert nudged_composite > base_composite

        # --- Reset clears overrides; composite returns to baseline ---
        r = await client.post("/preference/reset")
        assert r.status_code == 204, r.text

        r = await client.get("/preference/weights")
        rows = {row["dimension"]: row for row in r.json()}
        assert rows["compensation"]["override"] == 0

        assert abs(await _composite(orchestrator) - 0.5) < 1e-9

        # Explain no longer reports overrides either.
        r = await client.get("/preference/explain")
        assert r.status_code == 200, r.text
        assert r.json()["weight_overrides"] == {}

    Base.metadata.drop_all(engine)
