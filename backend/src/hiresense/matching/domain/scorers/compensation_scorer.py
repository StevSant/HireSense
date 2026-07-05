from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class CompensationScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "compensation"

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        location = (
            job.get("location", "") if isinstance(job, dict) else getattr(job, "location", "")
        )
        salary_range = (
            job.get("salary_range", "")
            if isinstance(job, dict)
            else getattr(job, "salary_range", "")
        )
        description = (
            job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        )

        salary_display = salary_range if salary_range else "Not specified"

        return (
            f"Job Title: {title}\n"
            f"Company: {company}\n"
            f"Location: {location}\n"
            f"Salary Range: {salary_display}\n"
            f"Description:\n{description}\n\n"
            "Evaluate the compensation competitiveness of this role. "
            "Consider the salary range against market rates for the location and role level. "
            "If no salary is specified, infer from company size, role, and location. "
            "A score of 1.0 means highly competitive; 0.0 means well below market. "
            'Return JSON: {"score": <float>, "rationale": "<brief>"}.'
        )
