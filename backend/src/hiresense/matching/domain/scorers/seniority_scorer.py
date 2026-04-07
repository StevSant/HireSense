from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class SeniorityScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "seniority_fit"

    def _build_system(self) -> str:
        return (
            "You are an expert job fit evaluator. Analyze job postings and rate seniority fit "
            "for a mid-senior backend/AI engineer with 3-5 years of experience. "
            "Respond with JSON only: {\"score\": <0.0-1.0>, \"rationale\": \"<brief explanation>\"}."
        )

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")

        return (
            f"Job Title: {title}\n"
            f"Company: {company}\n"
            f"Description:\n{description}\n\n"
            "Evaluate the seniority level this role targets. "
            "Rate the fit for a mid-senior backend/AI engineer with 3-5 years of experience. "
            "A score of 1.0 means a perfect match for that experience level; "
            "0.0 means this is for juniors or very senior staff only. "
            "Return JSON: {\"score\": <float>, \"rationale\": \"<brief>\"}."
        )
