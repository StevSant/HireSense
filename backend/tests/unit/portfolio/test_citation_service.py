import pytest

from hiresense.portfolio.domain import (
    PortfolioCitationService,
    PortfolioProject,
    ProjectText,
    RelevantProjectSelector,
)


class _FakeRepo:
    def __init__(self, projects):
        self._projects = projects

    def list_all(self):
        return self._projects


def _project(key, tech, *, demo=None):
    return PortfolioProject(
        id=key,
        source="supabase",
        source_key=key,
        tech=tech,
        url=f"https://github.com/x/{key}",
        demo_url=demo,
        translations={
            "en": ProjectText(title=key.title(), description="Did things."),
            "es": ProjectText(title=f"{key.title()} ES", description="Hizo cosas."),
        },
    )


def _service(projects, *, public_url="https://site.dev", ref_prefix="hiresense"):
    return PortfolioCitationService(
        repository=_FakeRepo(projects),
        selector=RelevantProjectSelector(),
        language="en",
        top_n=2,
        public_url=public_url,
        ref_prefix=ref_prefix,
    )


@pytest.mark.asyncio
async def test_citation_includes_projects_and_tracked_link() -> None:
    service = _service([_project("api", ["fastapi", "python"], demo="https://demo.x")])
    text = await service.citation_for(job_skills=["python"], job_text="", application_id="app-1")
    assert text is not None
    assert "Api [fastapi, python]: Did things." in text
    assert "https://github.com/x/api" in text
    assert "https://site.dev/?ref=hiresense-app-1" in text


@pytest.mark.asyncio
async def test_citation_none_when_no_relevant_projects_or_empty_snapshot() -> None:
    service = _service([_project("api", ["fastapi"])])
    assert await service.citation_for(job_skills=["unity"], job_text="", application_id="a") is None
    empty = _service([])
    assert await empty.citation_for(job_skills=["python"], job_text="", application_id="a") is None


@pytest.mark.asyncio
async def test_language_override_and_linkless_mode() -> None:
    service = _service([_project("api", ["python"])], public_url="")
    text = await service.citation_for(
        job_skills=["python"], job_text="", application_id="a", language="es"
    )
    assert text is not None
    assert "Api ES" in text
    assert "?ref=" not in text
