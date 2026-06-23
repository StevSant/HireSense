import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_auth
from hiresense.infrastructure.database import Base
from hiresense.autopilot.infrastructure import AutopilotDraftOrm  # noqa: F401


@pytest.mark.asyncio
async def test_autopilot_drafts_route_mounted(monkeypatch):
    db_url = "sqlite:///file::memory:?cache=shared&uri=true"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PORTFOLIO_SOURCES", "")
    monkeypatch.setenv("AUTOPILOT_PIPELINE_ENABLED", "true")

    setup_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "uri": True},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(setup_engine)

    from hiresense.main import create_app

    app = create_app()
    app.dependency_overrides[require_auth] = lambda: "u"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/autopilot/drafts")
    assert resp.status_code == 200

    setup_engine.dispose()
