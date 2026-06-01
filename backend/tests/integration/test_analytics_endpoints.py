from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.analytics.api import router as analytics_router
from hiresense.analytics.api.dependencies import get_analytics_service
from hiresense.analytics.domain import (
    AnalyticsService,
    FunnelService,
    MarketIntelService,
    SalaryParser,
    SkillGapService,
    SkillNormalizer,
    TargetSalaryService,
    TtlCache,
)
from hiresense.analytics.infrastructure import CorpusAnalyticsRepository
from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401
from hiresense.tracking.domain.models import TrackedApplication
from hiresense.tracking.infrastructure.orm import TrackedApplicationOrm  # noqa: F401
from hiresense.tracking.infrastructure.status_history_orm import ApplicationStatusHistoryOrm  # noqa: F401
from hiresense.tracking.infrastructure.repository import TrackingRepository


class _FakeProfile:
    def get_for_language(self, language):
        return type("V", (), {"skills": ["python"], "summary": "backend engineer"})()


class _Emb:
    async def embed(self, texts):
        return [[0.1, 0.2, 0.3]]


class _Store:
    async def search(self, query_embedding, *, top_k=10, filters=None):
        return []  # no similar jobs in this fixture → target-salary insufficient


def _factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed(factory):
    with factory() as s:
        s.add(IngestedJob(id="1", bucket="boards", source="x", source_type="board", title="A",
                          skills=["Python", "React"], remote_modality="remote",
                          salary_range="$100k-$120k", status="open", identity_key="k1",
                          posted_date=datetime(2026, 5, 1, tzinfo=timezone.utc)))
        s.commit()
    repo = TrackingRepository(session_factory=factory)
    app = repo.create(TrackedApplication(title="A", company="Acme", status="saved"))
    app.status = "applied"
    repo.save_with_history(app, from_status="saved", to_status="applied")
    return repo


def _build_app(factory, history):
    corpus = CorpusAnalyticsRepository(session_factory=factory)
    norm, sal = SkillNormalizer(), SalaryParser()
    service = AnalyticsService(
        funnel=FunnelService(history),
        market=MarketIntelService(corpus, norm, sal),
        skill_gap=SkillGapService(corpus, norm),
        target_salary=TargetSalaryService(embedding=_Emb(), vector_store=_Store(), corpus=corpus,
                                          salary_parser=sal, top_k=50, min_sample=5),
        profile_service=_FakeProfile(),
        cache=TtlCache(ttl_seconds=300),
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_analytics_service] = lambda: service
    app.include_router(analytics_router)
    return app


@pytest.mark.asyncio
async def test_funnel_endpoint():
    factory = _factory()
    history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/funnel")
        assert r.status_code == 200
        data = r.json()
        reached = {s["stage"]: s["reached"] for s in data["stages"]}
        assert reached["applied"] == 1 and reached["saved"] == 1
        assert data["total_applications"] == 1


@pytest.mark.asyncio
async def test_market_endpoint():
    factory = _factory()
    history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/market")
        assert r.status_code == 200
        data = r.json()
        assert any(s["skill"] == "python" for s in data["top_skills"])
        assert data["salary_distribution"]["currency"] == "USD"


@pytest.mark.asyncio
async def test_skill_gap_endpoint():
    factory = _factory()
    history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/skill-gap")
        assert r.status_code == 200
        data = r.json()
        assert data["has_profile"] is True
        # market has python+react; profile has python → react is a gap
        assert any(g["skill"] == "react" for g in data["missing"])


@pytest.mark.asyncio
async def test_target_salary_insufficient():
    factory = _factory()
    history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/target-salary")
        assert r.status_code == 200
        assert r.json()["insufficient_data"] is True  # _Store returns no matches
