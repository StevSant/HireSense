import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
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
    app.include_router(router)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/profile/nonexistent")
    assert resp.status_code == 404
