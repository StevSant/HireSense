"""Tests for the "You know someone here" connections badge on the jobs list.

Task 5, Phase 4 — connections count on the jobs list (backend).
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.ingestion.api import get_ingestion_orchestrator, get_portal_scanner, router
from hiresense.ingestion.api.dependencies import get_semantic_scoring
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.network.api.dependencies import get_contacts_repository
from hiresense.profile.api.dependencies import get_profile_service


class FakeProfileService:
    async def list_profiles(self):
        return []


ACME_JOB = NormalizedJob(
    id="acme-1",
    title="Backend Engineer",
    company="Acme Inc.",
    description="Backend role at Acme",
    skills=["python"],
    location="Remote",
    source="remotive",
    source_type="api",
    language="en",
    url="https://example.com/acme",
)

OTHER_JOB = NormalizedJob(
    id="other-1",
    title="Frontend Engineer",
    company="Other Corp",
    description="Frontend role at Other",
    skills=["javascript"],
    location="Remote",
    source="remotive",
    source_type="api",
    language="en",
    url="https://example.com/other",
)


class FakeOrchestrator:
    def list_jobs(self, criteria=None) -> list[NormalizedJob]:
        return [ACME_JOB, OTHER_JOB]

    async def run(self, filters=None) -> list[NormalizedJob]:
        return []

    def persist_scores(self, job_id, match_score, semantic_score) -> None:
        pass

    def persist_scores_batch(self, updates) -> None:
        pass


class FakeScanner:
    def list_jobs(self, criteria=None) -> list[NormalizedJob]:
        return []

    def get_job_by_id(self, job_id):
        return None

    def persist_scores(self, job_id, match_score, semantic_score) -> None:
        pass

    def persist_scores_batch(self, updates) -> None:
        pass


class FakeContactsRepository:
    """Fake ContactsRepositoryPort: always returns 2 connections for 'acme'."""

    def count_by_companies(self, companies_normalized: list[str]) -> dict[str, int]:
        result = {}
        for key in companies_normalized:
            if key == "acme":
                result[key] = 2
        return result

    def replace_all(self, contacts):
        return 0

    def list_all(self, company=None):
        return []

    def find_by_company(self, company_normalized):
        return []

    def last_imported_at(self):
        return None


def _make_app_with_network() -> FastAPI:
    """App wired with a fake contacts repository."""
    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: FakeOrchestrator()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    app.dependency_overrides[get_contacts_repository] = lambda: FakeContactsRepository()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


def _make_app_without_network() -> FastAPI:
    """Bare app — no contacts repository override (dependency returns None)."""
    app = FastAPI()
    app.dependency_overrides[get_ingestion_orchestrator] = lambda: FakeOrchestrator()
    app.dependency_overrides[get_portal_scanner] = lambda: FakeScanner()
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()
    app.dependency_overrides[get_semantic_scoring] = lambda: None
    # No get_contacts_repository override — returns None via bare app.state
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_connections_badge_populated_for_matching_company() -> None:
    """Page containing Acme Inc. and Other Corp: only Acme job gets a badge."""
    app = _make_app_with_network()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=boards")

    assert resp.status_code == 200
    data = resp.json()

    connections = data["connections_by_job"]
    # Acme Inc. normalizes to "acme" → count 2
    assert connections.get("acme-1") == 2
    # Other Corp has no connections → absent from the dict
    assert "other-1" not in connections


@pytest.mark.asyncio
async def test_connections_badge_empty_without_network_module() -> None:
    """When no contacts repository is wired, connections_by_job is empty and request succeeds."""
    app = _make_app_without_network()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/ingestion/jobs?tab=boards")

    assert resp.status_code == 200
    data = resp.json()
    assert data["connections_by_job"] == {}
