from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from hiresense.identity.api.dependencies import require_auth
from hiresense.profile.api.routes import router, get_profile_service
from hiresense.profile.domain.models import CandidateProfile, CVSection


class FakeProfileService:
    async def parse_and_create(self, tex_content: str, language: str = "en") -> CandidateProfile:
        return CandidateProfile(
            id="profile-1",
            name="Test User",
            email="test@example.com",
            sections=[CVSection(name="SUMMARY", content="A developer")],
            raw_tex=tex_content,
            language=language,
            skills=["python", "fastapi"],
        )

    async def get_profile(self, profile_id: str) -> CandidateProfile | None:
        if profile_id == "profile-1":
            return CandidateProfile(
                id="profile-1",
                name="Test User",
                email="test@example.com",
                sections=[],
                raw_tex="",
                language="en",
                skills=["python"],
            )
        return None


@pytest.mark.asyncio
async def test_upload_cv() -> None:
    app = FastAPI()
    fake = FakeProfileService()
    app.dependency_overrides[get_profile_service] = lambda: fake
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/profile/upload",
            json={"tex_content": "\\documentclass{article}...", "language": "en"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "profile-1"
    assert data["name"] == "Test User"
    assert "python" in data["skills"]


@pytest.mark.asyncio
async def test_get_profile_found() -> None:
    app = FastAPI()
    fake = FakeProfileService()
    app.dependency_overrides[get_profile_service] = lambda: fake
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/profile/profile-1")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test User"


@pytest.mark.asyncio
async def test_get_profile_not_found() -> None:
    app = FastAPI()
    fake = FakeProfileService()
    app.dependency_overrides[get_profile_service] = lambda: fake
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/profile/nonexistent")
    assert resp.status_code == 404


def _upload_app() -> FastAPI:
    app = FastAPI()
    app.state.settings = SimpleNamespace(max_upload_bytes=10 * 1024 * 1024)
    app.dependency_overrides[get_profile_service] = lambda: FakeProfileService()
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_upload_file_rejects_pdf_with_wrong_magic() -> None:
    app = _upload_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/profile/upload-file",
            files={"file": ("cv.pdf", b"not really a pdf", "application/pdf")},
        )
    assert resp.status_code == 400
    assert "does not match" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_file_rejects_binary_tex() -> None:
    app = _upload_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/profile/upload-file",
            files={"file": ("cv.tex", b"\xff\xfe\x00binary", "text/x-tex")},
        )
    assert resp.status_code == 400
    assert "not valid UTF-8" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_requires_auth_without_token() -> None:
    """Router-level auth: requests with no bearer token are rejected."""
    app = FastAPI()
    app.include_router(router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/profile/current")
    assert resp.status_code == 401
