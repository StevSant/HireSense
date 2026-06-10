import pytest

from hiresense.ingestion.api.routes import _gather_profile


class _FakeProfileService:
    async def list_profiles(self):
        class _Section:
            content = "CV summary text"

        class _Profile:
            skills = ["python"]
            sections = [_Section()]

        return [_Profile()]


class _FakeEnrichment:
    async def enrichment(self):
        return ["angular", "supabase"], "Portfolio projects:\n- HireSense [python]"


@pytest.mark.asyncio
async def test_gather_profile_without_enrichment_unchanged() -> None:
    skills, summary = await _gather_profile(_FakeProfileService())
    assert skills == ["python"]
    assert summary == "CV summary text"


@pytest.mark.asyncio
async def test_gather_profile_appends_portfolio_enrichment() -> None:
    skills, summary = await _gather_profile(_FakeProfileService(), _FakeEnrichment())
    assert skills == ["python", "angular", "supabase"]
    assert summary.endswith("Portfolio projects:\n- HireSense [python]")
    assert "CV summary text" in summary
