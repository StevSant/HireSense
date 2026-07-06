from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.research.api.dependencies import get_company_research_service
from hiresense.research.api.routes import router
from hiresense.research.domain.models import CompanyResearch


# ---------------------------------------------------------------------------
# Fake service
# ---------------------------------------------------------------------------


class FakeCompanyResearchService:
    def __init__(self) -> None:
        self._store: dict[str, CompanyResearch] = {}

    def _make_record(self, company_name: str, **overrides) -> CompanyResearch:
        record = CompanyResearch(
            company_name=company_name.strip(),
            funding_stage=overrides.get("funding_stage", "Series A"),
            tech_stack=overrides.get("tech_stack", "Python, FastAPI"),
            culture_summary=overrides.get("culture_summary", "Collaborative culture"),
            growth_trajectory=overrides.get("growth_trajectory", "Growing fast"),
            red_flags=overrides.get("red_flags", None),
            pros=overrides.get("pros", "Great benefits"),
            cons=overrides.get("cons", "Long hours"),
            raw_llm_response="{}",
        )
        record.id = uuid.uuid4()
        self._store[company_name.lower()] = record
        return record

    async def research(self, company_name: str, job_description: str = "") -> CompanyResearch:
        key = company_name.lower()
        if key in self._store:
            return self._store[key]
        return self._make_record(company_name)

    async def refresh(self, company_name: str, job_description: str = "") -> CompanyResearch:
        return self._make_record(company_name, funding_stage="Series B")

    def get(self, company_name: str) -> CompanyResearch | None:
        return self._store.get(company_name.lower())

    async def get_or_create(self, company_name: str, job_description: str = "") -> CompanyResearch:
        key = company_name.lower()
        if key in self._store:
            return self._store[key]
        return self._make_record(company_name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(fake_service: FakeCompanyResearchService) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_company_research_service] = lambda: fake_service
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_research_company() -> None:
    fake = FakeCompanyResearchService()
    client = TestClient(make_app(fake))

    resp = client.post("/research", json={"company_name": "Anthropic"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "Anthropic"
    assert data["funding_stage"] == "Series A"
    assert "id" in data


def test_research_with_job_description() -> None:
    fake = FakeCompanyResearchService()
    client = TestClient(make_app(fake))

    resp = client.post(
        "/research",
        json={
            "company_name": "OpenAI",
            "job_description": "We are looking for a backend engineer.",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "OpenAI"
    assert data["tech_stack"] == "Python, FastAPI"


def test_refresh_company() -> None:
    fake = FakeCompanyResearchService()
    client = TestClient(make_app(fake))

    resp = client.post("/research/refresh", json={"company_name": "Anthropic"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "Anthropic"
    assert data["funding_stage"] == "Series B"


def test_get_cached_research() -> None:
    fake = FakeCompanyResearchService()
    fake._make_record("Anthropic")
    client = TestClient(make_app(fake))

    resp = client.get("/research/Anthropic")

    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "Anthropic"


def test_get_generates_on_first_visit() -> None:
    fake = FakeCompanyResearchService()
    client = TestClient(make_app(fake))

    resp = client.get("/research/nonexistent")

    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "nonexistent"
    for key in ("industry", "company_size", "headquarters", "website", "logo_url"):
        assert key in data
