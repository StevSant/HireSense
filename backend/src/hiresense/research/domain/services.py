from __future__ import annotations

import json
import re
from typing import Any

from hiresense.research.domain.firmographics import Firmographics
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
        # Fetch source firmographics up front so they can both ground the prompt
        # and be surfaced even when no LLM is configured.
        firmographics = await self._fetch_firmographics(company_name)
        description = firmographics.description if firmographics is not None else None

        if self._llm is None:
            return self._make_fallback(company_name, _FALLBACK_LLM_NOT_CONFIGURED, firmographics)

        prompt = self._build_prompt(company_name, job_description, firmographics)
        try:
            response = await self._llm.complete(
                prompt, system="You are a company research analyst. Return only valid JSON."
            )
            data = self._parse_response(response)

            def _pick(field: str):
                if firmographics is not None:
                    val = getattr(firmographics, field)
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
                return self._with_description(self._repo.save(existing), description)
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
            return self._with_description(self._repo.create(record), description)
        except Exception:
            return self._make_fallback(company_name, _FALLBACK_RESEARCH_UNAVAILABLE, firmographics)

    async def _fetch_firmographics(self, company_name: str) -> Firmographics | None:
        """Firmographics are enrichment — a provider failure must never fail
        research, so swallow errors and proceed without them."""
        if self._firmographics is None:
            return None
        try:
            return await self._firmographics.fetch(company_name)
        except Exception:
            return None

    @staticmethod
    def _with_description(record: CompanyResearch, description: str | None) -> CompanyResearch:
        """Re-attach the transient source description dropped by persistence."""
        record.description = description
        return record

    def _build_prompt(
        self, company_name: str, job_description: str, firmographics: Firmographics | None = None
    ) -> str:
        prompt = (
            "You are a company research analyst.\n\n"
            f"Research the following company: {company_name}\n"
        )
        profile_block = self._format_profile(firmographics)
        if profile_block:
            prompt += profile_block
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

    @staticmethod
    def _format_profile(firmographics: Firmographics | None) -> str:
        """Render captured source facts as a grounding block, or '' if none.

        A verified profile from the job board is the antidote to the LLM branding
        small/non-US companies as shells for lack of parametric recall — so it is
        stated as ground truth with an explicit instruction not to claim
        insufficient information when a profile is present.
        """
        if firmographics is None:
            return ""
        facts = [
            ("About", firmographics.description),
            ("Industry", firmographics.industry),
            ("Company size", firmographics.company_size),
            ("Headquarters", firmographics.headquarters),
            ("Website", firmographics.website),
        ]
        lines = [f"{label}: {value}" for label, value in facts if value]
        if not lines:
            return ""
        body = "\n".join(lines)
        return (
            "\nKnown company profile from the job-board source (verified — may be "
            "in Spanish or another language). Treat this as ground truth and base "
            "your assessment on it; do NOT claim insufficient public information "
            f"or infer a lack of public presence when a profile is provided:\n{body}\n"
        )

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
    def _make_fallback(
        company_name: str, reason: str, firmographics: Firmographics | None = None
    ) -> CompanyResearch:
        record = CompanyResearch(
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
        if firmographics is not None:
            # Surface whatever the source gave us even without an LLM: the About
            # text and firmographic facts don't depend on generation.
            record.industry = firmographics.industry
            record.company_size = firmographics.company_size
            record.headquarters = firmographics.headquarters
            record.website = firmographics.website
            record.description = firmographics.description
        return record
