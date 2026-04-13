import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "pass")
    monkeypatch.setenv("JWT_SECRET_KEY", "secret")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    from hiresense.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

    from hiresense.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
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

    from hiresense.main import create_app

    app = create_app()
    routes = [r.path for r in app.routes]
    assert "/health" in routes
    assert "/auth/login" in routes
    assert "/ingestion/fetch" in routes
    assert "/matching/analyze" in routes
    assert "/optimization/optimize" in routes
    assert "/profile/upload" in routes
