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


# ---- PATCH /profile/{id} ------------------------------------------------

_VALID_PROFILE_UUID = "11111111-1111-1111-1111-111111111111"


class FakePatchService:
    """Captures what update_profile is called with so route semantics can be asserted."""

    def __init__(self, profile_exists: bool = True) -> None:
        self.profile_exists = profile_exists
        self.calls: list[tuple[str, dict[str, str | None]]] = []

    async def update_profile(
        self, profile_id, fields: dict[str, str | None]
    ) -> CandidateProfile | None:
        self.calls.append((str(profile_id), dict(fields)))
        if not self.profile_exists:
            return None
        return CandidateProfile(
            id=str(profile_id),
            name="Parsed Name",
            email=None,
            phone=None,
            location="Parsed Location",
            sections=[],
            raw_tex="",
            language="en",
            skills=[],
            name_override=fields.get("name_override"),
            location_override=fields.get("location_override"),
            linkedin_url=fields.get("linkedin_url"),
            github_url=fields.get("github_url"),
            portfolio_url=fields.get("portfolio_url"),
        )


def _patch_app(fake: FakePatchService) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_profile_service] = lambda: fake
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_patch_sets_each_field() -> None:
    fake = FakePatchService()
    app = _patch_app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/profile/{_VALID_PROFILE_UUID}",
            json={
                "name_override": "Bryan P.",
                "location_override": "Quito, Ecuador",
                "linkedin_url": "https://linkedin.com/in/bryan",
                "github_url": "https://github.com/bryan",
                "portfolio_url": "https://bryan.dev",
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name_override"] == "Bryan P."
    assert body["location_override"] == "Quito, Ecuador"
    assert body["linkedin_url"] == "https://linkedin.com/in/bryan"
    assert body["github_url"] == "https://github.com/bryan"
    assert body["portfolio_url"] == "https://bryan.dev"


@pytest.mark.asyncio
async def test_patch_omitted_field_is_not_sent_to_service() -> None:
    """Omitted keys must NOT appear in the dict passed to the service so the
    underlying repo preserves them rather than nulling."""
    fake = FakePatchService()
    app = _patch_app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.patch(
            f"/profile/{_VALID_PROFILE_UUID}",
            json={"linkedin_url": "https://linkedin.com/in/bryan"},
        )
    assert len(fake.calls) == 1
    _, fields = fake.calls[0]
    assert set(fields.keys()) == {"linkedin_url"}


@pytest.mark.asyncio
async def test_patch_null_is_forwarded_to_service() -> None:
    """Explicit null must be passed through so the repo clears the field."""
    fake = FakePatchService()
    app = _patch_app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.patch(
            f"/profile/{_VALID_PROFILE_UUID}",
            json={"linkedin_url": None},
        )
    _, fields = fake.calls[0]
    assert fields == {"linkedin_url": None}


@pytest.mark.asyncio
async def test_patch_rejects_non_http_url() -> None:
    fake = FakePatchService()
    app = _patch_app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/profile/{_VALID_PROFILE_UUID}",
            json={"linkedin_url": "ftp://nope.com"},
        )
    assert resp.status_code == 422
    assert "http" in resp.json()["detail"].lower()
    # Service must not have been called.
    assert fake.calls == []


@pytest.mark.asyncio
async def test_patch_unknown_profile_404() -> None:
    fake = FakePatchService(profile_exists=False)
    app = _patch_app(fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"/profile/{_VALID_PROFILE_UUID}",
            json={"name_override": "x"},
        )
    assert resp.status_code == 404
