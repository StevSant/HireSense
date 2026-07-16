from __future__ import annotations

from typing import Any

from hiresense.matching.domain.scorers.llm_scorer import BaseLLMScorer


class SeniorityScorer(BaseLLMScorer):
    @property
    def dimension_name(self) -> str:
        return "seniority_fit"

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        description = (
            job.get("description", "") if isinstance(job, dict) else getattr(job, "description", "")
        )
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")

        profile_context = ""
        if profile:
            skills = ", ".join(getattr(profile, "skills", []))
            experience = ""
            for section in getattr(profile, "sections", []):
                if hasattr(section, "name") and "experience" in section.name.lower():
                    experience = section.content[:500]
                    break
            profile_context = f"\nCandidate Skills: {skills}\nCandidate Experience: {experience}\n"

        return (
            "Analyze this job posting for seniority level. Rate how well it fits "
            "the candidate's experience level based on their profile (or a general mid-level "
            "engineer if no profile is provided).\n"
            "Score 0.0 (terrible fit) to 1.0 (perfect fit).\n"
            'Return JSON: {"score": <float>, "rationale": "<1-2 sentences>"}\n\n'
            f"Title: {title}\nCompany: {company}\n"
            f"Description: {self._truncate(description)}"
            f"{profile_context}"
        )
