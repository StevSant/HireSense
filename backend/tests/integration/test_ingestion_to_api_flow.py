"""Integration test: ingestion → SQL persistence → HTTP list endpoint.

Exercises the WIRED system across layers with a real (sqlite) database and the
real FastAPI route — not unit mocks: a real IngestionOrchestrator runs a fetch
that normalizes + upserts into a real JobsRepository, then the real
`GET /ingestion/jobs` route reads them back through filter/pagination.

This is the first occupant of the previously-empty integration tier (#19 item 4).
A true e2e tier against Postgres + pgvector (ANN search, migrations) is still a
follow-up — sqlite here verifies the request/persistence flow without the vector
backend.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.ingestion.api import (
    get_ingestion_orchestrator,
    get_portal_scanner,
    router,
)
from hiresense.ingestion.api.dependencies import get_semantic_scoring
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.ingestion.infrastructure import JobsRepository
from hiresense.ingestion.infrastructure.models import IngestedJob  # noqa: F401 (registers table)
from hiresense.kernel.value_objects import SourceType
from hiresense.profile.api.dependencies import get_profile_service


class _FakeBus:
    async def publish(self, event) -> None:  # noqa: ARG002
        pass


class _FakeSource:
    """A real-shaped JobSource returning two postings (no network)."""

    def source_name(self) -> str:
        return "remotive"

    def source_type(self) -> SourceType:
        return SourceType.API

    def supports_snapshot_closure(self) -> bool:
        return False

    async def fetch_jobs(self, filters=None) -> list[RawJobListing]:  # noqa: ARG002
        return [
            RawJobListing(source="remotive", source_id="101",
                          raw_data={"title": "Backend Engineer", "company": "Acme",
                                    "url": "https://e.com/101"}),
            RawJobListing(source="remotive", source_id="102",
                          raw_data={"title": "Frontend Engineer", "company": "Beta",
                                    "url": "https://e.com/102"}),
        ]


class _Normalizer:
    def normalize(self, raw: RawJobListing) -> dict:
        return {
            "title": raw.raw_data["title"],
            "company": raw.raw_data["company"],
            "description": "Build things",
            "skills": [],
            "location": "Remote",
            "salary_range": None,
            "url": raw.raw_data["url"],
            "language": "en",
        }


class _FakeProfileService:
    async def list_profiles(self):
        return []


class _EmptyScanner:
    def list_jobs(self, criteria=None):
        return []

    def get_job_by_id(self, job_id):  # noqa: ARG002
        return None


@pytest.mark.asyncio
async def test_ingested_jobs_persist_and_surface_via_api() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    repo = JobsRepository(session_factory=session_factory, bucket="boards")

    orchestrator = IngestionOrchestrator(
        sources=[_FakeSource()],
        normalizers={"remotive": _Normalizer()},
        event_bus=_FakeBus(),
        repository=repo,
        cooldown_seconds=0,
    )

    # 1) Ingest end-to-end: fetch → normalize → upsert → sqlite.
    new_jobs = await orchestrator.run()
    assert len(new_jobs) == 2

    # 2) Read them back through the REAL HTTP route over the same repo.
    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: orchestrator
    app.dependency_overrides[get_portal_scanner] = lambda: _EmptyScanner()
    app.dependency_overrides[get_profile_service] = lambda: _FakeProfileService()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs", params={"tab": "boards", "min_score": 0})

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    titles = {j["title"] for j in body["jobs"]}
    assert titles == {"Backend Engineer", "Frontend Engineer"}
    assert all(j["status"] == "open" for j in body["jobs"])

    Base.metadata.drop_all(engine)
