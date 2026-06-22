import pytest
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.main import create_app


@pytest.mark.asyncio
async def test_notifications_status_mounted():
    app = create_app()
    app.dependency_overrides[require_auth] = lambda: "u"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/notifications/status")
    assert resp.status_code == 200
    assert "enabled" in resp.json()
