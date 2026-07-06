from __future__ import annotations

import json

import pytest

from hiresense.research.domain import CompanyResearchService, Firmographics


class _FakeRepo:
    def get_by_company_name(self, name):
        return None

    def create(self, r):
        return r

    def save(self, r):
        return r


class _FakeLLM:
    async def complete(self, prompt, system=""):
        return json.dumps(
            {
                "funding_stage": "Seed",
                "tech_stack": "Go",
                "culture_summary": "c",
                "growth_trajectory": "g",
                "red_flags": None,
                "pros": "p",
                "cons": "c",
                "industry": "LLM-industry",
                "company_size": None,
                "headquarters": "LLM-HQ",
                "website": "https://llm.example",
            }
        )


class _FakeProvider:
    async def fetch(self, company_name):
        return Firmographics(industry="Provider-industry", company_size="201-500")


@pytest.mark.asyncio
async def test_external_wins_llm_fills_gaps():
    svc = CompanyResearchService(
        repository=_FakeRepo(), llm=_FakeLLM(), firmographics=_FakeProvider()
    )
    r = await svc.research("BC")
    assert r.industry == "Provider-industry"  # external wins
    assert r.company_size == "201-500"  # external wins
    assert r.headquarters == "LLM-HQ"  # gap filled by LLM
    assert r.website == "https://llm.example"  # gap filled by LLM
