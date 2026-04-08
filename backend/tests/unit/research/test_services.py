from __future__ import annotations

import json

import pytest

from hiresense.research.domain.models import CompanyResearch
from hiresense.research.domain.services import CompanyResearchService


class FakeLLM:
    def __init__(self, response: str) -> None:
        self._response = response
        self.call_count = 0
        self.last_prompt: str = ""

    async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
        self.call_count += 1
        self.last_prompt = prompt
        return self._response


class FakeRepo:
    def __init__(self) -> None:
        self._store: dict[str, CompanyResearch] = {}
        self.created: list[CompanyResearch] = []
        self.saved: list[CompanyResearch] = []

    def get_by_company_name(self, company_name: str) -> CompanyResearch | None:
        return self._store.get(company_name.lower().strip())

    def create(self, research: CompanyResearch) -> CompanyResearch:
        self.created.append(research)
        self._store[research.company_name.lower().strip()] = research
        return research

    def save(self, research: CompanyResearch) -> CompanyResearch:
        self.saved.append(research)
        self._store[research.company_name.lower().strip()] = research
        return research


_LLM_RESPONSE = json.dumps({
    "funding_stage": "Series D",
    "tech_stack": "Python, Rust",
    "culture_summary": "AI safety focused",
    "growth_trajectory": "Rapid growth",
    "red_flags": None,
    "pros": "Great mission",
    "cons": "High intensity",
})


@pytest.mark.asyncio
async def test_research_calls_llm_and_persists() -> None:
    llm = FakeLLM(_LLM_RESPONSE)
    repo = FakeRepo()
    service = CompanyResearchService(repository=repo, llm=llm)

    result = await service.research("Anthropic")

    assert llm.call_count == 1
    assert len(repo.created) == 1
    assert result.company_name == "Anthropic"
    assert result.funding_stage == "Series D"
    assert result.pros == "Great mission"


@pytest.mark.asyncio
async def test_research_returns_cached() -> None:
    llm = FakeLLM(_LLM_RESPONSE)
    repo = FakeRepo()
    service = CompanyResearchService(repository=repo, llm=llm)

    first = await service.research("Anthropic")
    second = await service.research("Anthropic")

    assert llm.call_count == 1
    assert first.company_name == second.company_name
    assert len(repo.created) == 1


@pytest.mark.asyncio
async def test_research_includes_job_description_in_prompt() -> None:
    llm = FakeLLM(_LLM_RESPONSE)
    repo = FakeRepo()
    service = CompanyResearchService(repository=repo, llm=llm)

    await service.research("Anthropic", job_description="We need a backend engineer")

    assert "We need a backend engineer" in llm.last_prompt


@pytest.mark.asyncio
async def test_refresh_overwrites_cached() -> None:
    llm = FakeLLM(_LLM_RESPONSE)
    repo = FakeRepo()
    service = CompanyResearchService(repository=repo, llm=llm)

    await service.research("Anthropic")
    assert llm.call_count == 1

    await service.refresh("Anthropic")
    assert llm.call_count == 2


@pytest.mark.asyncio
async def test_research_no_llm_returns_fallback_not_persisted() -> None:
    repo = FakeRepo()
    service = CompanyResearchService(repository=repo, llm=None)

    result = await service.research("Anthropic")

    assert result.funding_stage == "LLM not configured"
    assert result.pros == "LLM not configured"
    assert len(repo.created) == 0


@pytest.mark.asyncio
async def test_research_llm_failure_returns_fallback_not_persisted() -> None:
    class FailingLLM:
        async def complete(self, prompt: str, *, system: str = "", model: str = "") -> str:
            raise RuntimeError("API down")

    repo = FakeRepo()
    service = CompanyResearchService(repository=repo, llm=FailingLLM())

    result = await service.research("Anthropic")

    assert result.funding_stage == "Research unavailable"
    assert result.pros == "Research unavailable"
    assert len(repo.created) == 0


@pytest.mark.asyncio
async def test_get_returns_cached() -> None:
    llm = FakeLLM(_LLM_RESPONSE)
    repo = FakeRepo()
    service = CompanyResearchService(repository=repo, llm=llm)

    await service.research("Anthropic")
    result = service.get("Anthropic")

    assert result is not None
    assert result.company_name == "Anthropic"


def test_get_returns_none_when_not_cached() -> None:
    repo = FakeRepo()
    service = CompanyResearchService(repository=repo, llm=None)

    result = service.get("NonExistentCorp")

    assert result is None
