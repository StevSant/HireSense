import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    # Pin the optional portfolio module OFF — env vars beat dotenv, so this
    # keeps app boot deterministic regardless of the developer's local .env.
    monkeypatch.setenv("PORTFOLIO_SOURCES", "")

    from hiresense.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    # Drive the app lifespan so setup_telemetry's providers are shut down on
    # exit (otherwise their console-exporter background threads outlive the test
    # and write to pytest's closed stdout at interpreter teardown).
    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_login_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "testpass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    # Pin the optional portfolio module OFF — env vars beat dotenv, so this
    # keeps app boot deterministic regardless of the developer's local .env.
    monkeypatch.setenv("PORTFOLIO_SOURCES", "")

    from hiresense.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    # Drive the app lifespan so setup_telemetry's providers are shut down on
    # exit (otherwise their console-exporter background threads outlive the test
    # and write to pytest's closed stdout at interpreter teardown).
    async with app.router.lifespan_context(app), AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/auth/login", json={"username": "admin", "password": "testpass"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_all_routers_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    # Pin the optional portfolio module OFF — env vars beat dotenv, so this
    # keeps app boot deterministic regardless of the developer's local .env.
    # The portfolio router is mounted unconditionally, so the /portfolio/*
    # route assertions below still hold with the module disabled.
    monkeypatch.setenv("PORTFOLIO_SOURCES", "")

    from hiresense.main import create_app

    app = create_app()
    # Drive the lifespan so telemetry providers are shut down on exit (see note
    # in the client-based tests above).
    async with app.router.lifespan_context(app):
        routes = [r.path for r in app.routes]
    assert "/health" in routes
    assert "/auth/login" in routes
    assert "/ingestion/fetch" in routes
    assert "/matching/analyze" in routes
    assert "/optimization/optimize" in routes
    assert "/profile/upload" in routes
    assert "/portfolio/sync" in routes
    assert "/portfolio/projects" in routes
    assert "/network/import" in routes
