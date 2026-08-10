from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer
from hiresense.matching.prompts import GROWTH_POTENTIAL


class GrowthScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "growth_potential"

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        description = (
            job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        )
        skills = job.get("skills", []) if isinstance(job, dict) else getattr(job, "skills", [])

        skills_display = ", ".join(skills) if skills else "Not specified"

        return (
            f"Job Title: {title}\n"
            f"Company: {company}\n"
            f"Required Skills: {skills_display}\n"
            f"Description:\n{self._truncate(description)}\n\n"
            f"{GROWTH_POTENTIAL.bulleted()}"
        )
