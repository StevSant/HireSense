import pytest

from hiresense.portfolio.domain import PortfolioProject, PortfolioSyncService, ProjectText


def _project(key: str, source: str) -> PortfolioProject:
    return PortfolioProject(
        id=key,
        source=source,
        source_key=key,
        translations={"en": ProjectText(title=key)},
    )


class _FakeSource:
    def __init__(self, name: str, projects=None, error: Exception | None = None):
        self._name, self._projects, self._error = name, projects or [], error

    def source_name(self) -> str:
        return self._name

    async def fetch_projects(self):
        if self._error:
            raise self._error
        return self._projects


class _FakeRepo:
    def __init__(self):
        self.slices: dict[str, list] = {}

    def replace_source(self, source, projects):
        self.slices[source] = projects
        return len(projects)


@pytest.mark.asyncio
async def test_sync_replaces_each_sources_slice() -> None:
    repo = _FakeRepo()
    service = PortfolioSyncService(
        sources=[_FakeSource("supabase", [_project("a", "supabase")])], repository=repo
    )
    result = await service.sync()
    assert result.counts_by_source == {"supabase": 1}
    assert result.errors == {}
    assert [p.source_key for p in repo.slices["supabase"]] == ["a"]


@pytest.mark.asyncio
async def test_failing_source_is_isolated() -> None:
    repo = _FakeRepo()
    service = PortfolioSyncService(
        sources=[
            _FakeSource("supabase", error=RuntimeError("boom")),
            _FakeSource("github", [_project("r", "github")]),
        ],
        repository=repo,
    )
    result = await service.sync()
    assert result.counts_by_source == {"github": 1}
    assert "boom" in result.errors["supabase"]
    assert "supabase" not in repo.slices  # previous slice untouched
