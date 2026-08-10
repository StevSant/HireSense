from __future__ import annotations

import logging
from typing import Any

from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.kernel import extract_json
from hiresense.matching.domain.scorers.llm_scorer import truncate_job_text
from hiresense.matching.prompts import DIMENSION_NAMES, render_combined_system_prompt
from hiresense.ports import LLMPort

logger = logging.getLogger(__name__)


def _field(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class CombinedDimensionScorer:
    """Scores all 6 matching dimensions in one LLM call.

    A drop-in replacement for fanning out to the 6 individual BaseLLMScorer
    subclasses (seniority, compensation, growth, culture, application
    strength, interview readiness): one prompt, one response, ~1/6th the LLM
    calls per job. `score_all` returns None on any failure (no LLM configured,
    the call raising, or a response that doesn't parse into all 6 dimensions)
    so the caller can fall back to the per-dimension fan-out.

    Returned `DimensionResult.weight` is a placeholder (0) — the caller owns
    the configured per-dimension weights and must apply them.
    """

    def __init__(self, llm: LLMPort | None, job_char_limit: int = 4000) -> None:
        self._llm = llm
        self._job_char_limit = job_char_limit

    async def score_all(self, job: Any, profile: Any | None = None) -> list[DimensionResult] | None:
        if self._llm is None:
            return None
        try:
            prompt = self._build_prompt(job, profile)
            response = await self._llm.complete(prompt, system=render_combined_system_prompt())
        except Exception as exc:
            logger.warning("Combined dimension scorer LLM call failed: %s", exc)
            return None
        return self._parse(response)

    def _build_prompt(self, job: Any, profile: Any | None = None) -> str:
        title = _field(job, "title")
        company = _field(job, "company")
        location = _field(job, "location")
        salary_range = _field(job, "salary_range") or "Not specified"
        skills = _field(job, "skills", [])
        skills_display = ", ".join(skills) if skills else "Not specified"
        description = truncate_job_text(_field(job, "description"), self._job_char_limit)

        job_section = (
            "JOB\n"
            f"Title: {title}\n"
            f"Company: {company}\n"
            f"Location: {location}\n"
            f"Salary Range: {salary_range}\n"
            f"Required Skills: {skills_display}\n"
            f"Description:\n{description}"
        )
        return f"{job_section}\n\n{self._candidate_section(profile)}"

    def _candidate_section(self, profile: Any | None) -> str:
        if profile is None:
            return "CANDIDATE\nNo candidate profile provided."
        skills = ", ".join(getattr(profile, "skills", []) or []) or "Not specified"
        sections_text = ""
        for section in getattr(profile, "sections", []) or []:
            name = getattr(section, "name", "")
            content = getattr(section, "content", "")
            sections_text += f"\n{name}:\n{content}\n"
        return f"CANDIDATE\nSkills: {skills}\nCV Sections:{sections_text or ' (none)'}"

    def _parse(self, response: str) -> list[DimensionResult] | None:
        data = extract_json(response)
        if not isinstance(data, dict):
            return None
        entries = data.get("dimensions")
        if not isinstance(entries, list):
            return None

        by_name: dict[str, DimensionResult] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = entry.get("dimension")
            if name not in DIMENSION_NAMES or name in by_name:
                continue
            try:
                score = float(entry["score"])
            except (KeyError, TypeError, ValueError):
                continue
            by_name[name] = DimensionResult(
                dimension=name,
                score=score,
                rationale=str(entry.get("rationale", "")),
                weight=0,
            )

        if len(by_name) != len(DIMENSION_NAMES):
            return None
        return [by_name[d] for d in DIMENSION_NAMES]
