from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.research.api import router as research_router
from hiresense.research.api.dependencies import get_company_research_service
from hiresense.research.domain import CompanyResearchService
from hiresense.research.infrastructure import CompanyResearchRepository
from hiresense.research.infrastructure.orm import CompanyResearchOrm  # noqa: F401


def _factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def _build_app(logo_service_url: str = "https://logo.x/{domain}") -> FastAPI:
    repo = CompanyResearchRepository(session_factory=_factory())
    # llm=None → the service falls back to a not-configured record (matches the
    # local, no-LLM test config), which is enough to exercise get-or-create.
    service = CompanyResearchService(repository=repo, llm=None)

    app = FastAPI()
    app.state.settings = type("Settings", (), {"logo_service_url": logo_service_url})()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_company_research_service] = lambda: service
    app.include_router(research_router)
    return app


@pytest.fixture
def app() -> FastAPI:
    return _build_app()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_get_research_returns_intel_fields_and_does_not_404(client):
    resp = await client.get("/research/SomeCo")

    assert resp.status_code == 200
    body = resp.json()
    assert body["company_name"] == "SomeCo"
    for key in ("industry", "company_size", "headquarters", "website", "logo_url"):
        assert key in body


@pytest.mark.asyncio
async def test_get_research_is_idempotent_get_or_create(client):
    first = await client.get("/research/SomeCo")
    second = await client.get("/research/SomeCo")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


@pytest.mark.asyncio
async def test_post_research_attaches_logo_url_when_website_present(app: FastAPI):
    # Seed a record with a website directly through the repository so the
    # logo_url derivation has something to work with (the no-LLM fallback
    # path never sets a website).
    service = app.dependency_overrides[get_company_research_service]()
    from hiresense.research.domain.models import CompanyResearch

    record = CompanyResearch(
        company_name="Acme",
        funding_stage="Series A",
        tech_stack="Python",
        culture_summary="Great",
        growth_trajectory="Growing",
        red_flags=None,
        pros="Good",
        cons="Bad",
        website="https://www.acme.com/careers",
        raw_llm_response="{}",
    )
    service._repo.create(record)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/research/Acme")

    assert resp.status_code == 200
    body = resp.json()
    assert body["website"] == "https://www.acme.com/careers"
    assert body["logo_url"] == "https://logo.x/acme.com"


@pytest.mark.asyncio
async def test_logo_url_none_when_service_url_not_configured():
    app = _build_app(logo_service_url="")
    service = app.dependency_overrides[get_company_research_service]()
    from hiresense.research.domain.models import CompanyResearch

    record = CompanyResearch(
        company_name="Acme",
        funding_stage="Series A",
        tech_stack="Python",
        culture_summary="Great",
        growth_trajectory="Growing",
        red_flags=None,
        pros="Good",
        cons="Bad",
        website="https://www.acme.com/careers",
        raw_llm_response="{}",
    )
    service._repo.create(record)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/research/Acme")

    assert resp.status_code == 200
    assert resp.json()["logo_url"] is None
