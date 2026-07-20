from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class CultureScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "culture_fit"

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        location = (
            job.get("location", "") if isinstance(job, dict) else getattr(job, "location", "")
        )
        description = (
            job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        )

        return (
            f"Job Title: {title}\n"
            f"Company: {company}\n"
            f"Location / Work Mode: {location}\n"
            f"Description:\n{self._truncate(description)}\n\n"
            "Evaluate the culture fit of this role. Consider:\n"
            "- Remote, hybrid, or on-site flexibility\n"
            "- Work-life balance signals in the description\n"
            "- Collaboration style (team-oriented vs. solo)\n"
            "- Company values and mission alignment\n"
            "A score of 1.0 means excellent culture alignment; 0.0 means poor fit. "
            'Return JSON: {"score": <float>, "rationale": "<brief>"}.'
        )
