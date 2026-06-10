from __future__ import annotations

import io
import types
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.network.api import router
from hiresense.network.api.dependencies import get_contacts_repository, get_import_service
from hiresense.network.domain import Contact

_HEADER = "First Name,Last Name,URL,Email Address,Company,Position,Connected On"
_VALID_CSV = (_HEADER + "\nJordan,Lee,,sam@x.dev,Acme Inc.,EM,01 Feb 2025\n").encode("utf-8")


class _FakeRepo:
    def __init__(self, contacts: list[Contact] | None = None) -> None:
        self._contacts: list[Contact] = contacts or []
        self._imported_at: datetime | None = None

    def replace_all(self, contacts: list[Contact]) -> int:
        self._contacts = contacts
        self._imported_at = datetime.now(timezone.utc)
        return len(contacts)

    def list_all(self, company: str | None = None) -> list[Contact]:
        if company is not None:
            from hiresense.network.domain import normalize_company

            key = normalize_company(company)
            return [c for c in self._contacts if c.company_normalized == key]
        return list(self._contacts)

    def find_by_company(self, company_normalized: str) -> list[Contact]:
        return [c for c in self._contacts if c.company_normalized == company_normalized]

    def count_by_companies(self, companies_normalized: list[str]) -> dict[str, int]:
        return {}

    def last_imported_at(self) -> datetime | None:
        return self._imported_at


class _FakeImportService:
    def __init__(self, repo: _FakeRepo) -> None:
        self._repo = repo

    async def import_upload(self, payload: bytes, *, filename: str) -> int:
        from hiresense.network.domain import parse_connections

        contacts = parse_connections(payload, filename=filename)
        return self._repo.replace_all(contacts)

    async def last_imported_at(self) -> datetime | None:
        return self._repo.last_imported_at()


_SETTINGS = types.SimpleNamespace(max_upload_bytes=10 * 1024 * 1024)


def _app(service=None, repo=None) -> FastAPI:
    app = FastAPI()
    app.state.settings = _SETTINGS
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_import_service] = lambda: service
    app.dependency_overrides[get_contacts_repository] = lambda: repo
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_requires_auth_without_token() -> None:
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        assert (await client.get("/network/contacts")).status_code == 401


@pytest.mark.asyncio
async def test_import_happy_path() -> None:
    repo = _FakeRepo()
    svc = _FakeImportService(repo)
    app = _app(service=svc, repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/network/import",
            files={"file": ("Connections.csv", _VALID_CSV, "text/csv")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["contacts"] == 1
    assert body["imported_at"] is not None
    assert len(repo._contacts) == 1
    assert repo._contacts[0].first_name == "Jordan"


@pytest.mark.asyncio
async def test_import_rejects_wrong_extension() -> None:
    repo = _FakeRepo()
    svc = _FakeImportService(repo)
    app = _app(service=svc, repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/network/import",
            files={"file": ("connections.txt", _VALID_CSV, "text/plain")},
        )

    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_rejects_oversized() -> None:
    repo = _FakeRepo()
    svc = _FakeImportService(repo)
    app = FastAPI()
    app.state.settings = types.SimpleNamespace(max_upload_bytes=10)  # tiny limit
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.dependency_overrides[get_import_service] = lambda: svc
    app.dependency_overrides[get_contacts_repository] = lambda: repo
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/network/import",
            files={"file": ("Connections.csv", _VALID_CSV, "text/csv")},
        )

    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_import_rejects_zip_without_pk_magic() -> None:
    repo = _FakeRepo()
    svc = _FakeImportService(repo)
    app = _app(service=svc, repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/network/import",
            files={"file": ("export.zip", b"this is not a zip file", "application/zip")},
        )

    assert resp.status_code == 400
    assert "does not match" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_import_503_when_service_none() -> None:
    app = _app(service=None, repo=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/network/import",
            files={"file": ("Connections.csv", _VALID_CSV, "text/csv")},
        )

    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_import_400_on_parse_error() -> None:
    repo = _FakeRepo()
    svc = _FakeImportService(repo)
    app = _app(service=svc, repo=repo)

    # Valid .csv extension but no connections header
    bad_csv = b"not,a,connections,file\n1,2,3,4\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/network/import",
            files={"file": ("Connections.csv", bad_csv, "text/csv")},
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_contacts_with_repo() -> None:
    contacts = [
        Contact(first_name="Jordan", last_name="Lee", company="Acme Inc."),
        Contact(first_name="Sam", last_name="Diaz", company="Globant S.A."),
    ]
    repo = _FakeRepo(contacts)
    app = _app(repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/network/contacts")

    assert resp.status_code == 200
    assert len(resp.json()["contacts"]) == 2


@pytest.mark.asyncio
async def test_contacts_without_repo() -> None:
    app = _app(repo=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/network/contacts")

    assert resp.status_code == 200
    assert resp.json() == {"contacts": []}


@pytest.mark.asyncio
async def test_contacts_filtered_by_company() -> None:
    contacts = [
        Contact(first_name="Jordan", last_name="Lee", company="Acme Inc."),
        Contact(first_name="Sam", last_name="Diaz", company="Globant S.A."),
    ]
    repo = _FakeRepo(contacts)
    app = _app(repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/network/contacts", params={"company": "Acme Inc."})

    assert resp.status_code == 200
    result = resp.json()["contacts"]
    assert len(result) == 1
    assert result[0]["first_name"] == "Jordan"


@pytest.mark.asyncio
async def test_match_normalizes_company_query() -> None:
    """Contact stored under 'ACME, LLC' should be found via 'Acme Inc.' query."""
    contacts = [
        Contact(first_name="Jordan", last_name="Lee", company="ACME, LLC"),
    ]
    repo = _FakeRepo(contacts)
    app = _app(repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/network/match", params={"company": "Acme Inc."})

    assert resp.status_code == 200
    body = resp.json()
    assert body["company_normalized"] == "acme"
    assert len(body["contacts"]) == 1
    assert body["contacts"][0]["first_name"] == "Jordan"


@pytest.mark.asyncio
async def test_match_without_repo() -> None:
    app = _app(repo=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.get("/network/match", params={"company": "Stripe"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["company_normalized"] == "stripe"
    assert body["contacts"] == []


@pytest.mark.asyncio
async def test_import_valid_zip_export() -> None:
    """A proper ZIP containing Connections.csv is accepted and parsed."""
    repo = _FakeRepo()
    svc = _FakeImportService(repo)
    app = _app(service=svc, repo=repo)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("Basic_LinkedInDataExport/Connections.csv", _VALID_CSV)
    zip_bytes = buf.getvalue()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        resp = await client.post(
            "/network/import",
            files={"file": ("export.zip", zip_bytes, "application/zip")},
        )

    assert resp.status_code == 200
    assert resp.json()["contacts"] == 1
