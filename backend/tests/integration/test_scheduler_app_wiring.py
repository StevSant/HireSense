import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.scheduler.infrastructure import JobRunOrm, JobToggleOrm  # noqa: F401


@pytest.mark.asyncio
async def test_scheduler_router_is_mounted_and_lists_jobs(monkeypatch):
    # scheduler_enabled defaults False, so the APScheduler loop does NOT start,
    # but the provider + routes are still mounted and usable.
    #
    # Point shared_infra at a shared-cache in-memory SQLite DB so the scheduler
    # repositories can query tables that actually exist (Base.metadata is created
    # below on the same engine).
    db_url = "sqlite:///file::memory:?cache=shared&uri=true"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PORTFOLIO_SOURCES", "")

    # Create tables in the shared-cache DB so the session factory inside
    # create_app() can query scheduler_job_runs and scheduler_job_toggles.
    setup_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "uri": True},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(setup_engine)

    from hiresense.main import create_app

    app = create_app()
    app.dependency_overrides[require_auth] = lambda: "u"
    transport = ASGITransport(app=app)
    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://t") as client:
        resp = await client.get("/scheduler/jobs")
    assert resp.status_code == 200
    names = {j["name"] for j in resp.json()}
    assert {"ingestion_fetch", "revalidation_sweep", "autohunt_digest", "outreach_followups"}.issubset(names)

    setup_engine.dispose()
