import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_admin, require_auth
from hiresense.notifications.api import router as notifications_router
from hiresense.notifications.api.dependencies import get_notification_service
from hiresense.notifications.domain import NotificationService


class _Sender:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


def _build_app(to_email: str):
    service = NotificationService(sender=_Sender(), to_email=to_email)
    app = FastAPI()
    app.dependency_overrides[require_auth] = lambda: "u"
    app.dependency_overrides[require_admin] = lambda: {"role": "admin"}
    app.dependency_overrides[get_notification_service] = lambda: service
    app.include_router(notifications_router)
    return app


@pytest.mark.asyncio
async def test_status_reports_enabled_and_masked_recipient():
    app = _build_app("alice@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/notifications/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["recipient_masked"] is not None
    assert "alice@example.com" not in body["recipient_masked"]  # masked, not raw


@pytest.mark.asyncio
async def test_test_endpoint_sends_when_enabled():
    app = _build_app("alice@example.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post("/notifications/test")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_test_endpoint_503_when_disabled():
    app = _build_app("")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post("/notifications/test")
    assert resp.status_code == 503
