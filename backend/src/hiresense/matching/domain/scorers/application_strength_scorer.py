from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer
from hiresense.matching.prompts import APPLICATION_STRENGTH


class ApplicationStrengthScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "application_strength"

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

        experience_content = ""
        if profile:
            sections = getattr(profile, "sections", [])
            for section in sections:
                name = getattr(section, "name", "")
                if "EXPERIENCE" in name.upper():
                    experience_content = getattr(section, "content", "")
                    break

        return (
            f"Job Title: {title}\n"
            f"Company: {company}\n"
            f"Required Skills: {job_skills_display}\n"
            f"Job Description:\n{self._truncate(description)}\n\n"
            f"Candidate Skills: {candidate_skills_display}\n"
            f"Candidate Experience:\n{experience_content}\n\n"
            f"{APPLICATION_STRENGTH.bulleted()}"
        )

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult:
        if profile is None:
            return DimensionResult.default(
                self.dimension_name,
                weight=self._weight,
                rationale="No CV provided for evaluation",
            )
        return await super().score(job, profile)
