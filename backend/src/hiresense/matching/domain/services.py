from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from hiresense.kernel.contracts.matching import MatchCompletedEvent
from hiresense.matching.domain.models import MatchResult, ScoreBreakdown
from hiresense.matching.domain.semantic_scorer import SemanticScorer
from hiresense.matching.domain.skill_matcher import SkillMatcher

logger = logging.getLogger(__name__)


class MatchingOrchestrator:
    def __init__(self, llm: Any, event_bus: Any) -> None:
        self._llm = llm
        self._event_bus = event_bus
        self._semantic_scorer = SemanticScorer()
        self._skill_matcher = SkillMatcher()

    async def analyze(
        self,
        job_id: str,
        cv_id: str,
        job_description: str,
        job_skills: list[str],
        cv_summary: str,
        cv_skills: list[str],
        cv_embedding: list[float] | None = None,
        job_embedding: list[float] | None = None,
    ) -> MatchResult:
        # 1. Semantic score
        if cv_embedding and job_embedding:
            semantic_score = self._semantic_scorer.score(cv_embedding, job_embedding)
        else:
            semantic_score = 0.0

        # 2. Skill match
        skill_result = self._skill_matcher.match(cv_skills, job_skills)

        # 3. LLM analysis for experience, language, pros/cons
        llm_analysis = await self._get_llm_analysis(
            job_description, job_skills, cv_summary, cv_skills
        )

        # 4. Build breakdown
        breakdown = ScoreBreakdown(
            semantic_score=semantic_score,
            skill_score=skill_result.score,
            experience_score=llm_analysis.get("experience_score", 0.5),
            language_score=llm_analysis.get("language_score", 0.5),
        )

        match_id = str(uuid.uuid4())
        result = MatchResult(
            id=match_id,
            job_id=job_id,
            cv_id=cv_id,
            overall_score=breakdown.weighted_average(),
            breakdown=breakdown,
            matched_skills=skill_result.matched,
            missing_skills=skill_result.missing,
            pros=llm_analysis.get("pros", []),
            cons=llm_analysis.get("cons", []),
            recommendations=llm_analysis.get("recommendations", []),
        )

        # 5. Publish event
        event = MatchCompletedEvent(
            payload={
                "job_id": job_id,
                "match_id": match_id,
                "score": result.overall_score,
            }
        )
        await self._event_bus.publish(event)

        return result

    async def _get_llm_analysis(
        self,
        job_description: str,
        job_skills: list[str],
        cv_summary: str,
        cv_skills: list[str],
    ) -> dict[str, Any]:
        prompt = (
            "Analyze this job-candidate match.\n\n"
            f"Job Description: {job_description}\n"
            f"Required Skills: {', '.join(job_skills)}\n\n"
            f"Candidate Summary: {cv_summary}\n"
            f"Candidate Skills: {', '.join(cv_skills)}\n\n"
            "Return a JSON object with:\n"
            '- "experience_score": float 0-1\n'
            '- "language_score": float 0-1\n'
            '- "pros": list of strings\n'
            '- "cons": list of strings\n'
            '- "recommendations": list of strings\n'
            "Return ONLY valid JSON."
        )
        try:
            response = await self._llm.complete(
                prompt, system="You are a job matching analysis assistant."
            )
            return json.loads(response)
        except (json.JSONDecodeError, Exception):
            logger.exception("LLM analysis failed")
            return {
                "experience_score": 0.5,
                "language_score": 0.5,
                "pros": [],
                "cons": [],
                "recommendations": [],
            }
