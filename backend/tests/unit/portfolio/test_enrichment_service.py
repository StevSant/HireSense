import pytest

from hiresense.portfolio.domain import (
    PortfolioEnrichmentService,
    PortfolioProject,
    ProjectText,
)


class _FakeRepo:
    def __init__(self, projects):
        self._projects = projects

    def list_all(self):
        return self._projects


def _project(key: str, tech: list[str]) -> PortfolioProject:
    return PortfolioProject(
        id=key, source="supabase", source_key=key, tech=tech,
        translations={"en": ProjectText(title=key.title(), description="d")},
    )


@pytest.mark.asyncio
async def test_enrichment_unions_tech_and_builds_text() -> None:
    service = PortfolioEnrichmentService(
        repository=_FakeRepo([_project("a", ["Python", "angular"]), _project("b", ["python"])]),
        language="en",
        char_cap=500,
    )
    skills, text = await service.enrichment()
    assert skills == ["Python", "angular", "python"]  # union, sorted, case preserved
    assert text.startswith("Portfolio projects:")
    assert "- A [Python, angular]: d" in text


@pytest.mark.asyncio
async def test_enrichment_empty_snapshot() -> None:
    service = PortfolioEnrichmentService(repository=_FakeRepo([]), language="en", char_cap=500)
    assert await service.enrichment() == ([], "")
