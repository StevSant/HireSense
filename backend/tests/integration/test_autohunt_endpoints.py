from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.autohunt.api import router as autohunt_router
from hiresense.autohunt.api.dependencies import get_autohunt_service
from hiresense.autohunt.domain import AutoHuntService
from hiresense.autohunt.infrastructure import DigestRepository
from hiresense.autohunt.infrastructure.orm import DigestOrm  # noqa: F401
from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401
from hiresense.ingestion.infrastructure.jobs_repository import JobsRepository


class _PreRanker:
    async def rerank(self, jobs, skill_by_id, candidate_skills, candidate_summary, bucket):
        return sorted(jobs, key=lambda j: j.match_score or 0, reverse=True)


class _Profile:
    def get_for_language(self, language):
        return type("V", (), {"skills": ["python"], "summary": "backend"})()


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _seed_jobs(factory):
    # Use a fetched_at clearly in the past so the first-run watermark
    # (DigestOrm.created_at, second-precision via SQLite server_default)
    # is unambiguously newer than the seeded jobs.
    past = datetime.now(timezone.utc) - timedelta(seconds=5)
    with factory() as s:
        s.add_all(
            [
                IngestedJob(
                    id="hi",
                    bucket="boards",
                    source="x",
                    source_type="board",
                    title="High",
                    company="Acme",
                    url="http://x/hi",
                    identity_key="k1",
                    status="open",
                    fetched_at=past,
                    match_score=0.9,
                ),
                IngestedJob(
                    id="lo",
                    bucket="boards",
                    source="x",
                    source_type="board",
                    title="Low",
                    company="Acme",
                    url="http://x/lo",
                    identity_key="k2",
                    status="open",
                    fetched_at=past,
                    match_score=0.2,
                ),
            ]
        )
        s.commit()


def _build_app(factory):
    jobs_repo = JobsRepository(session_factory=factory, bucket="boards")
    service = AutoHuntService(
        jobs_repo=jobs_repo,
        pre_ranker=_PreRanker(),
        profile_service=_Profile(),
        digest_repo=DigestRepository(session_factory=factory),
        top_n=5,
        min_score=0.6,
        initial_lookback_days=7,
        retention_days=90,
        language="en",
    )
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_autohunt_service] = lambda: service
    app.include_router(autohunt_router)
    return app


@pytest.mark.asyncio
async def test_run_creates_digest_above_floor():
    factory = _factory()
    _seed_jobs(factory)
    app = _build_app(factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/autohunt/run")
        assert r.status_code == 200
        data = r.json()
        assert data["job_count"] == 1  # only the 0.9 job clears the 0.6 floor
        assert data["entries"][0]["job_id"] == "hi"


@pytest.mark.asyncio
async def test_second_run_empty_and_watermark_chains():
    factory = _factory()
    _seed_jobs(factory)
    app = _build_app(factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        first = (await c.post("/autohunt/run")).json()
        # No jobs newer than the first run's created_at → empty digest.
        second = (await c.post("/autohunt/run")).json()
        assert second["job_count"] == 0
        assert second["cutoff_at"][:19] == first["created_at"][:19]  # watermark chains
        latest = (await c.get("/autohunt/digests/latest")).json()
        assert latest["job_count"] == 0
        listed = (await c.get("/autohunt/digests?limit=10")).json()
        assert len(listed) == 2
