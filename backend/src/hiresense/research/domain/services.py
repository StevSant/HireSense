from __future__ import annotations

import json
import re
from typing import Any

from hiresense.research.domain.models import CompanyResearch
from hiresense.research.ports import CompanyResearchRepositoryPort

_FALLBACK_LLM_NOT_CONFIGURED = "LLM not configured"
_FALLBACK_RESEARCH_UNAVAILABLE = "Research unavailable"


class CompanyResearchService:
    def __init__(
        self, repository: CompanyResearchRepositoryPort, llm: Any = None, firmographics: Any = None
    ) -> None:
        self._repo = repository
        self._llm = llm
        self._firmographics = firmographics

    async def research(self, company_name: str, job_description: str = "") -> CompanyResearch:
        cached = self._repo.get_by_company_name(company_name)
        if cached is not None:
            return cached
        return await self._do_research(company_name, job_description)

    async def refresh(self, company_name: str, job_description: str = "") -> CompanyResearch:
        return await self._do_research(company_name, job_description)

    async def get_or_create(self, company_name: str, job_description: str = "") -> CompanyResearch:
        cached = self._repo.get_by_company_name(company_name)
        if cached is not None:
            return cached
        return await self._do_research(company_name, job_description)

    def get(self, company_name: str) -> CompanyResearch | None:
        return self._repo.get_by_company_name(company_name)

    async def _do_research(self, company_name: str, job_description: str) -> CompanyResearch:
        if self._llm is None:
            return self._make_fallback(company_name, _FALLBACK_LLM_NOT_CONFIGURED)

        prompt = self._build_prompt(company_name, job_description)
        try:
            response = await self._llm.complete(
                prompt, system="You are a company research analyst. Return only valid JSON."
            )
            data = self._parse_response(response)

            external = None
            if self._firmographics is not None:
                external = await self._firmographics.fetch(company_name)

            def _pick(field: str):
                if external is not None:
                    val = getattr(external, field)
                    if val:
                        return val
                return data.get(field)

            existing = self._repo.get_by_company_name(company_name)
            if existing is not None:
                existing.funding_stage = data["funding_stage"]
                existing.tech_stack = data["tech_stack"]
                existing.culture_summary = data["culture_summary"]
                existing.growth_trajectory = data["growth_trajectory"]
                existing.red_flags = data.get("red_flags")
                existing.pros = data["pros"]
                existing.cons = data["cons"]
                existing.industry = _pick("industry")
                existing.company_size = _pick("company_size")
                existing.headquarters = _pick("headquarters")
                existing.website = _pick("website")
                existing.raw_llm_response = response
                return self._repo.save(existing)
            record = CompanyResearch(
                company_name=company_name.strip(),
                funding_stage=data["funding_stage"],
                tech_stack=data["tech_stack"],
                culture_summary=data["culture_summary"],
                growth_trajectory=data["growth_trajectory"],
                red_flags=data.get("red_flags"),
                pros=data["pros"],
                cons=data["cons"],
                industry=_pick("industry"),
                company_size=_pick("company_size"),
                headquarters=_pick("headquarters"),
                website=_pick("website"),
                raw_llm_response=response,
            )
            return self._repo.create(record)
        except Exception:
            return self._make_fallback(company_name, _FALLBACK_RESEARCH_UNAVAILABLE)

    def _build_prompt(self, company_name: str, job_description: str) -> str:
        prompt = (
            "You are a company research analyst.\n\n"
            f"Research the following company: {company_name}\n"
        )
        if job_description:
            prompt += f"\nJob Description Context:\n{job_description[:2000]}\n"
        prompt += (
            "\nReturn a JSON object with the following fields:\n"
            "- funding_stage: string (e.g. Seed, Series A, Series B, Public, etc.)\n"
            "- tech_stack: string (technologies used)\n"
            "- culture_summary: string (company culture description)\n"
            "- growth_trajectory: string (growth and trajectory assessment)\n"
            "- red_flags: string or null (any concerns or red flags)\n"
            "- pros: string (benefits of working there)\n"
            "- cons: string (downsides of working there)\n"
            "- industry: string or null\n"
            "- company_size: string or null (e.g. '51-200')\n"
            "- headquarters: string or null (city, country)\n"
            "- website: string or null (official homepage URL)\n\n"
            'Return valid JSON only: {"funding_stage": "...", "tech_stack": "...", '
            '"culture_summary": "...", "growth_trajectory": "...", "red_flags": null, '
            '"pros": "...", "cons": "...", "industry": null, "company_size": null, '
            '"headquarters": null, "website": null}'
        )
        return prompt

    def _parse_response(self, response: str) -> dict:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        md = re.search(r"```(?:json)?\s*\n?({.*?})\s*\n?```", response, re.DOTALL)
        if md:
            return json.loads(md.group(1))
        raise ValueError("Could not parse LLM response as JSON")

    @staticmethod
    def _make_fallback(company_name: str, reason: str) -> CompanyResearch:
        return CompanyResearch(
            company_name=company_name.strip(),
            funding_stage=reason,
            tech_stack=reason,
            culture_summary=reason,
            growth_trajectory=reason,
            red_flags=reason,
            pros=reason,
            cons=reason,
            raw_llm_response="{}",
        )
