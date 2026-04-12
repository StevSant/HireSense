from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class GrowthScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "growth_potential"

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
        description = job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        skills = job.get("skills", []) if isinstance(job, dict) else getattr(job, "skills", [])

        skills_display = ", ".join(skills) if skills else "Not specified"

        return (
            f"Job Title: {title}\n"
            f"Company: {company}\n"
            f"Required Skills: {skills_display}\n"
            f"Description:\n{description}\n\n"
            "Evaluate the growth potential of this role. Consider:\n"
            "- Learning and skill development opportunities\n"
            "- Modernity of the tech stack\n"
            "- Mentorship and leadership exposure\n"
            "- Career trajectory and advancement potential\n"
            "A score of 1.0 means excellent growth prospects; 0.0 means stagnant/dead-end role. "
            'Return JSON: {"score": <float>, "rationale": "<brief>"}.'
        )
