"""Tests for /profile/cover-letter-templates CRUD routes."""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.profile.cover_letter_templates.dependencies import (
    get_cover_letter_template_service,
)
from hiresense.profile.cover_letter_templates.routes import router
from hiresense.profile.cover_letter_templates.view import CoverLetterTemplateView


def _view(name: str = "Concise", body: str = "Hi {{company}}, …") -> CoverLetterTemplateView:
    return CoverLetterTemplateView(
        id=uuid_mod.uuid4(),
        name=name,
        body=body,
        tone="professional",
        language="en",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class FakeTemplateService:
    def __init__(self) -> None:
        self.items: dict[uuid_mod.UUID, CoverLetterTemplateView] = {}
        self.deleted: list[uuid_mod.UUID] = []

    def list(self) -> list[CoverLetterTemplateView]:
        return list(self.items.values())

    def create(self, name, body, tone="professional", language="en"):
        if not name.strip() or not body.strip():
            raise ValueError("name and body must not be empty")
        v = CoverLetterTemplateView(
            id=uuid_mod.uuid4(),
            name=name.strip(),
            body=body,
            tone=tone,
            language=language,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.items[v.id] = v
        return v

    def update(self, template_id, fields):
        existing = self.items.get(template_id)
        if existing is None:
            return None
        if "name" in fields and not fields["name"].strip():
            raise ValueError("name must not be empty")
        if "body" in fields and not fields["body"].strip():
            raise ValueError("body must not be empty")
        updated = existing.model_copy(update=fields)
        self.items[template_id] = updated
        return updated

    def delete(self, template_id):
        if template_id not in self.items:
            return False
        del self.items[template_id]
        self.deleted.append(template_id)
        return True


def _app(service: FakeTemplateService) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_cover_letter_template_service] = lambda: service
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_list_returns_all_templates() -> None:
    service = FakeTemplateService()
    v = service.create(name="Concise", body="Hello")
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        resp = await client.get("/profile/cover-letter-templates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == str(v.id)


@pytest.mark.asyncio
async def test_create_returns_201_and_view() -> None:
    service = FakeTemplateService()
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/profile/cover-letter-templates",
            json={"name": "Concise", "body": "Hello", "tone": "concise"},
        )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Concise"
    assert resp.json()["tone"] == "concise"


@pytest.mark.asyncio
async def test_create_rejects_empty_name() -> None:
    service = FakeTemplateService()
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/profile/cover-letter-templates",
            json={"name": "   ", "body": "Hello"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_empty_body() -> None:
    service = FakeTemplateService()
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/profile/cover-letter-templates",
            json={"name": "Concise", "body": "  "},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_updates_fields() -> None:
    service = FakeTemplateService()
    v = service.create(name="Concise", body="Hello")
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        resp = await client.patch(
            f"/profile/cover-letter-templates/{v.id}",
            json={"name": "Renamed", "tone": "enthusiastic"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["tone"] == "enthusiastic"
    assert body["body"] == "Hello"  # preserved


@pytest.mark.asyncio
async def test_patch_unknown_404() -> None:
    service = FakeTemplateService()
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        resp = await client.patch(
            f"/profile/cover-letter-templates/{uuid_mod.uuid4()}",
            json={"name": "X"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_returns_204_and_removes() -> None:
    service = FakeTemplateService()
    v = service.create(name="Concise", body="Hello")
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        resp = await client.delete(f"/profile/cover-letter-templates/{v.id}")
    assert resp.status_code == 204
    assert v.id in service.deleted
    assert v.id not in service.items


@pytest.mark.asyncio
async def test_delete_unknown_404() -> None:
    service = FakeTemplateService()
    async with AsyncClient(
        transport=ASGITransport(app=_app(service)), base_url="http://test"
    ) as client:
        resp = await client.delete(f"/profile/cover-letter-templates/{uuid_mod.uuid4()}")
    assert resp.status_code == 404
