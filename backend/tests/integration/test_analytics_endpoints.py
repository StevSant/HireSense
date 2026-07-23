from datetime import datetime, timezone
from uuid import uuid4

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
    CompBenchmarkService,
    FunnelService,
    MarketIntelService,
    SalaryParser,
    SearchFocusService,
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
from hiresense.tracking.domain.status_transition import StatusTransition
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


class _StaticHistory:
    def __init__(self, rows):
        self._rows = rows

    def list_history(self):
        return self._rows


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed(factory):
    with factory() as s:
        s.add(
            IngestedJob(
                id="1",
                bucket="boards",
                source="x",
                source_type="board",
                title="A",
                skills=["Python", "React"],
                remote_modality="remote",
                salary_range="$100k-$120k",
                status="open",
                identity_key="k1",
                posted_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
            )
        )
        s.commit()
    repo = TrackingRepository(session_factory=factory)
    app = repo.create(TrackedApplication(title="A", company="Acme", status="saved"))
    app.status = "applied"
    repo.save_with_history(app, from_status="saved", to_status="applied")
    return repo


def _build_app(factory, history, tracking_read=None):
    corpus = CorpusAnalyticsRepository(session_factory=factory, sample_cap=5000)
    norm, sal = SkillNormalizer(), SalaryParser()
    service = AnalyticsService(
        funnel=FunnelService(history, applications_read=tracking_read, corpus=corpus),
        market=MarketIntelService(corpus, norm, sal),
        skill_gap=SkillGapService(corpus, norm),
        target_salary=TargetSalaryService(
            embedding=_Emb(),
            vector_store=_Store(),
            corpus=corpus,
            salary_parser=sal,
            top_k=50,
            min_sample=5,
        ),
        comp_benchmark=CompBenchmarkService(
            embedding=_Emb(),
            vector_store=_Store(),
            corpus=corpus,
            salary_parser=sal,
            tracking_read=tracking_read,
            top_k=50,
            min_sample=5,
        ),
        search_focus=SearchFocusService(
            embedding=_Emb(), vector_store=_Store(), corpus=corpus, top_k=50, fresh_days=14
        ),
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
        assert data["current_rejected"] == 0


@pytest.mark.asyncio
async def test_funnel_endpoint_rejects_an_inverted_period():
    factory = _factory()
    history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        response = await c.get(
            "/analytics/funnel",
            params={"start": "2026-05-03T00:00:00Z", "end": "2026-05-02T00:00:00Z"},
        )

    assert response.status_code == 422
    assert response.json()["detail"] == "start must be earlier than or equal to end"


@pytest.mark.asyncio
async def test_funnel_endpoint_returns_the_requested_historical_cohort():
    factory = _factory()
    before_window, in_window = uuid4(), uuid4()
    history = _StaticHistory(
        [
            StatusTransition(
                application_id=before_window,
                to_status="saved",
                changed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
            StatusTransition(
                application_id=before_window,
                to_status="applied",
                changed_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
            ),
            StatusTransition(
                application_id=in_window,
                to_status="saved",
                changed_at=datetime(2026, 5, 3, tzinfo=timezone.utc),
            ),
            StatusTransition(
                application_id=in_window,
                to_status="applied",
                changed_at=datetime(2026, 5, 5, tzinfo=timezone.utc),
            ),
            StatusTransition(
                application_id=in_window,
                to_status="interviewing",
                changed_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
            ),
        ]
    )
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        response = await c.get(
            "/analytics/funnel",
            params={"start": "2026-05-02T00:00:00Z", "end": "2026-05-06T00:00:00Z"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total_applications"] == 1
    reached = {stage["stage"]: stage["reached"] for stage in data["stages"]}
    assert reached["applied"] == 1
    assert reached["interviewing"] == 0


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
async def test_upskilling_plan_endpoint_uses_profile_aware_skill_gaps():
    factory = _factory()
    history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        response = await c.get("/analytics/upskilling-plan")

    assert response.status_code == 200
    data = response.json()
    assert data["has_profile"] is True
    assert data["steps"] == [
        {
            "skill": "react",
            "demand_count": 1,
            "demand_pct": 100.0,
            "next_action": "Learn the core concepts and vocabulary.",
        }
    ]


@pytest.mark.asyncio
async def test_target_salary_insufficient():
    factory = _factory()
    history = _seed(factory)
    app = _build_app(factory, history)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/target-salary")
        assert r.status_code == 200
        assert r.json()["insufficient_data"] is True  # _Store returns no matches


class _MatchStore:
    """Returns ANN results for the given ids (descending score)."""

    def __init__(self, ids):
        self._ids = ids

    async def search(self, query_embedding, *, top_k=10, filters=None):
        n = len(self._ids)
        return [
            type("R", (), {"id": jid, "score": 1.0 - i / max(n, 1)})()
            for i, jid in enumerate(self._ids)
        ]


def _seed_salaried(factory, n=6):
    """Seed n open jobs with parseable USD salaries + senior titles."""
    ids = [f"s{i}" for i in range(n)]
    with factory() as s:
        for i, jid in enumerate(ids):
            s.add(
                IngestedJob(
                    id=jid,
                    bucket="boards",
                    source="getonboard" if i % 2 else "linkedin",
                    source_type="board",
                    title=f"Senior Backend Engineer {i}",
                    description="Senior role, 5+ years",
                    skills=["python"],
                    remote_modality="remote" if i % 2 else "on_site",
                    salary_range=f"${100 + i * 5}k-${120 + i * 5}k",
                    status="open",
                    quality="ok",
                    identity_key=f"sk{i}",
                    company=f"Co{i}",
                    location="Remote" if i % 2 else "NYC",
                    posted_date=datetime.now(timezone.utc),
                )
            )
        s.commit()
    return ids


def _build_app_with_store(factory, history, store, tracking_read=None):
    corpus = CorpusAnalyticsRepository(session_factory=factory, sample_cap=5000)
    norm, sal = SkillNormalizer(), SalaryParser()
    service = AnalyticsService(
        funnel=FunnelService(history, applications_read=tracking_read, corpus=corpus),
        market=MarketIntelService(corpus, norm, sal),
        skill_gap=SkillGapService(corpus, norm),
        target_salary=TargetSalaryService(
            embedding=_Emb(),
            vector_store=store,
            corpus=corpus,
            salary_parser=sal,
            top_k=50,
            min_sample=5,
        ),
        comp_benchmark=CompBenchmarkService(
            embedding=_Emb(),
            vector_store=store,
            corpus=corpus,
            salary_parser=sal,
            tracking_read=tracking_read,
            top_k=50,
            min_sample=5,
        ),
        search_focus=SearchFocusService(
            embedding=_Emb(), vector_store=store, corpus=corpus, top_k=50, fresh_days=14
        ),
        profile_service=_FakeProfile(),
        cache=TtlCache(ttl_seconds=300),
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_analytics_service] = lambda: service
    app.include_router(analytics_router)
    return app


@pytest.mark.asyncio
async def test_comp_endpoint_returns_band_and_seniority():
    factory = _factory()
    history = _seed(factory)
    ids = _seed_salaried(factory, n=6)
    app = _build_app_with_store(factory, history, _MatchStore(ids))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/comp")
        assert r.status_code == 200
        data = r.json()
        assert data["insufficient_data"] is False
        assert data["currency"] == "USD"
        assert data["median_annual"] is not None
        assert data["ask_min_annual"] == data["median_annual"]
        # all 6 are "Senior ..." → a senior band with the full sample
        levels = {b["level"] for b in data["by_seniority"]}
        assert "senior" in levels


@pytest.mark.asyncio
async def test_focus_endpoint_aggregates_matches():
    factory = _factory()
    history = _seed(factory)
    ids = _seed_salaried(factory, n=6)
    app = _build_app_with_store(factory, history, _MatchStore(ids))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/analytics/focus")
        assert r.status_code == 200
        data = r.json()
        assert data["insufficient_data"] is False
        assert data["match_count"] == 6
        assert len(data["best_fit_companies"]) > 0
        # titles normalise to "Backend Engineer" (seniority stripped)
        assert any("Backend Engineer" in role["label"] for role in data["best_fit_roles"])
        assert data["remote_share"] is not None
        assert data["fresh_fit_count"] == 6  # all posted now
