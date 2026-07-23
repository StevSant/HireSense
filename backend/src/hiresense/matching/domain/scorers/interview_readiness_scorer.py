from __future__ import annotations

from typing import Any

from hiresense.claims.domain import CandidateClaimService
from hiresense.kernel.prompt_boundary import PromptBoundary
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class InterviewReadinessScorer(BaseLLMScorer):
    def __init__(
        self,
        llm: Any,
        weight: int,
        job_char_limit: int = 4000,
        claim_service: CandidateClaimService | None = None,
    ) -> None:
        super().__init__(llm=llm, weight=weight, job_char_limit=job_char_limit)
        self._claim_service = claim_service

    @property
    def dimension_name(self) -> str:
        return "interview_readiness"

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        description = (
            job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        )
        job_skills = job.get("skills", []) if isinstance(job, dict) else getattr(job, "skills", [])

        job_skills_display = ", ".join(job_skills) if job_skills else "Not specified"

        candidate_skills = getattr(profile, "skills", []) if profile else []
        candidate_skills_display = (
            ", ".join(candidate_skills) if candidate_skills else "Not specified"
        )

        sections_text = ""
        if profile:
            sections = getattr(profile, "sections", [])
            for section in sections:
                name = getattr(section, "name", "")
                content = getattr(section, "content", "")
                sections_text += f"\n{name}:\n{content}\n"

        verified_evidence = self._format_verified_evidence()

        return (
            f"Job Title: {title}\n"
            f"Company: {company}\n"
            f"Required Skills: {job_skills_display}\n"
            f"Job Description:\n{self._truncate(description)}\n\n"
            f"Candidate Skills: {candidate_skills_display}\n"
            f"CV Sections:{sections_text}\n"
            f"Verified candidate evidence:\n{verified_evidence}\n"
            "Evaluate this candidate's interview readiness for the role. Consider:\n"
            "- Availability of strong STAR (Situation, Task, Action, Result) story material\n"
            "- Technical depth and evidence of hands-on expertise\n"
            "- Potential weak spots or gaps that could be probed in interviews\n"
            "A score of 1.0 means the candidate is very well prepared; 0.0 means poorly prepared. "
            'Return JSON: {"score": <float>, "rationale": "<brief>"}.'
        )

    def _format_verified_evidence(self) -> str:
        if self._claim_service is None:
            return "None available."
        claims = self._claim_service.list_verified_for_readiness()
        if not claims:
            return "None available."
        evidence = "\n".join(
            f"- {claim.text}\n  {claim.source}: {claim.provenance}" for claim in claims
        )
        return PromptBoundary.trusted_candidate_facts(evidence, max_chars=6000)

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult:
        if profile is None:
            return DimensionResult.default(
                self.dimension_name,
                weight=self._weight,
                rationale="No CV provided for evaluation",
            )
        return await super().score(job, profile)
