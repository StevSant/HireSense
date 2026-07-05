import pytest

from hiresense.portfolio.domain import (
    PortfolioEnrichmentService,
    PortfolioProject,
    ProjectText,
)


class _FakeRepo:
    def __init__(self, projects):
        self._projects = projects

    def list_for_matching(self):
        return [p for p in self._projects if p.include_in_matching]


def _project(key: str, tech: list[str], include_in_matching: bool = True) -> PortfolioProject:
    return PortfolioProject(
        id=key,
        source="supabase",
        source_key=key,
        tech=tech,
        include_in_matching=include_in_matching,
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


@pytest.mark.asyncio
async def test_enrichment_excludes_projects_opted_out_of_matching() -> None:
    service = PortfolioEnrichmentService(
        repository=_FakeRepo(
            [
                _project("a", ["python"]),
                _project("b", ["rust"], include_in_matching=False),
            ]
        ),
        language="en",
        char_cap=500,
    )
    skills, text = await service.enrichment()
    assert skills == ["python"]  # rust from the opted-out project is absent
    assert "B " not in text and "rust" not in text
