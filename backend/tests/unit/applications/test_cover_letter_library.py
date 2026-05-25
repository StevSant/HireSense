"""Tests for GET /applications/cover-letters — cross-app library route."""
from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.applications.api.dependencies import (
    get_application_service,
    get_artifact_service,
)
from hiresense.applications.api.routes import router
from hiresense.applications.domain.aggregate import CoverLetterLibraryItem
from hiresense.identity.api.dependencies import require_auth


class FakeService:
    def __init__(self, items: list[CoverLetterLibraryItem]) -> None:
        self._items = items

    def list_all_cover_letters(self) -> list[CoverLetterLibraryItem]:
        return list(self._items)


def _client(service: FakeService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_auth] = lambda: True
    app.dependency_overrides[get_application_service] = lambda: service
    # Stub the artifact dependency so router import doesn't blow up even though we don't use it.
    app.dependency_overrides[get_artifact_service] = lambda: object()
    return TestClient(app)


def _item(*, title: str, company: str, body: str, status: str = "applied") -> CoverLetterLibraryItem:
    return CoverLetterLibraryItem(
        id=uuid_mod.uuid4(),
        application_id=uuid_mod.uuid4(),
        job_title=title,
        company=company,
        body=body,
        tone="professional",
        application_status=status,
        created_at=datetime.now(timezone.utc),
    )


def test_empty_library_returns_empty_list() -> None:
    client = _client(FakeService([]))
    resp = client.get("/applications/cover-letters")
    assert resp.status_code == 200
    assert resp.json() == []


def test_library_returns_items_with_app_metadata() -> None:
    items = [
        _item(title="Backend Engineer", company="Acme", body="Hello Acme"),
        _item(title="Frontend Engineer", company="Globex", body="Hello Globex"),
    ]
    client = _client(FakeService(items))
    resp = client.get("/applications/cover-letters")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # The route preserves whatever order the service returns (service is responsible for ordering).
    titles = {row["job_title"] for row in data}
    assert titles == {"Backend Engineer", "Frontend Engineer"}
    first = data[0]
    assert {"id", "application_id", "job_title", "company", "body", "tone", "application_status"} <= set(first.keys())


def test_cover_letters_path_is_not_swallowed_by_uuid_route() -> None:
    """Regression: /applications/cover-letters MUST be matched before /{application_id}.
    If route order is wrong this would return 422 (invalid UUID)."""
    client = _client(FakeService([]))
    resp = client.get("/applications/cover-letters")
    assert resp.status_code == 200, (
        f"Expected 200; got {resp.status_code}. If 422, the cover-letters route is "
        "declared AFTER /{application_id} and FastAPI is parsing it as a UUID."
    )
