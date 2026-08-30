import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from hiresense.identity.api.dependencies import require_auth
from hiresense.shared.infrastructure.database import Base
from hiresense.submission.infrastructure import SubmissionAttemptOrm  # noqa: F401


def _base_env(monkeypatch, db_url):
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("PORTFOLIO_SOURCES", "")


def _make_app(db_url):
    setup_engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False, "uri": True},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(setup_engine)

    from hiresense.main import create_app

    app = create_app()
    app.dependency_overrides[require_auth] = lambda: "u"
    return app, setup_engine


@pytest.mark.asyncio
async def test_submission_routes_absent_when_disabled(monkeypatch):
    db_url = "sqlite:///file:subdisabled?mode=memory&cache=shared&uri=true"
    _base_env(monkeypatch, db_url)
    monkeypatch.setenv("AUTOPILOT_SUBMIT_ENABLED", "false")

    app, engine = _make_app(db_url)
    try:
        paths = {getattr(route, "path", "") for route in app.routes}
        assert not any(p.startswith("/submission") for p in paths)
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_submission_routes_mounted_when_enabled(monkeypatch):
    db_url = "sqlite:///file:subenabled?mode=memory&cache=shared&uri=true"
    _base_env(monkeypatch, db_url)
    monkeypatch.setenv("AUTOPILOT_SUBMIT_ENABLED", "true")

    app, engine = _make_app(db_url)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            resp = await client.get("/submission/attempts")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        engine.dispose()
