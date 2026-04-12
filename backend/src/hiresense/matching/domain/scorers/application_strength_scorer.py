from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class ApplicationStrengthScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "application_strength"

    def _output_schema(self) -> type[BaseModel]:
        return DimensionResult

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        job_skills = job.get("skills", []) if isinstance(job, dict) else getattr(job, "skills", [])

        job_skills_display = ", ".join(job_skills) if job_skills else "Not specified"

        candidate_skills = getattr(profile, "skills", []) if profile else []
        candidate_skills_display = ", ".join(candidate_skills) if candidate_skills else "Not specified"

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
            f"Job Description:\n{description}\n\n"
            f"Candidate Skills: {candidate_skills_display}\n"
            f"Candidate Experience:\n{experience_content}\n\n"
            "Evaluate how well this candidate's CV positions them for the role. Consider:\n"
            "- Skill overlap between candidate and job requirements\n"
            "- Relevance and quality of experience\n"
            "- How compellingly the CV tells their story for this role\n"
            "A score of 1.0 means the CV is an excellent match; 0.0 means very poor fit. "
            'Return JSON: {"score": <float>, "rationale": "<brief>"}.'
        )

    async def score(self, job: Any, profile: Any | None = None) -> DimensionResult:
        if profile is None:
            return DimensionResult.default(
                self.dimension_name,
                weight=self._weight,
                rationale="No CV provided for evaluation",
            )
        return await super().score(job, profile)
