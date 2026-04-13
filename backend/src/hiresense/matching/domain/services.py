from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel

from hiresense.kernel.events import MatchCompletedEvent
from hiresense.matching.domain.models import MatchResult, ScoreBreakdown
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.semantic_scorer import SemanticScorer
from hiresense.matching.domain.skill_matcher import SkillMatcher

logger = logging.getLogger(__name__)


class EvaluationResult(BaseModel):
    composite_score: float
    job_title: str
    company: str
    dimensions: list[DimensionResult]


class MatchingOrchestrator:
    def __init__(
        self,
        llm: Any,
        event_bus: Any,
        dimension_scorers: list[Any] | None = None,
        embedding: Any | None = None,
    ) -> None:
        self._llm = llm
        self._event_bus = event_bus
        self._dimension_scorers = dimension_scorers or []
        self._embedding = embedding
        self._semantic_scorer = SemanticScorer()
        self._skill_matcher = SkillMatcher()

    async def evaluate(self, job: Any, profile: Any | None = None, dimension_scorers: list[Any] | None = None) -> EvaluationResult:
        scorers = dimension_scorers if dimension_scorers is not None else self._dimension_scorers
        title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
        company = job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")

        async def safe_score(scorer: Any) -> DimensionResult:
            try:
                return await scorer.score(job, profile)
            except Exception as exc:
                return DimensionResult(dimension=scorer.dimension_name, score=0.5, rationale=f"Evaluation failed: {exc}", weight=scorer.weight)

        results = await asyncio.gather(*[safe_score(s) for s in scorers])
        dimensions = list(results)
        total_weight = sum(d.weight for d in dimensions)
        composite = sum(d.score * d.weight for d in dimensions) / total_weight if total_weight > 0 else 0.5

        return EvaluationResult(composite_score=round(composite, 4), job_title=title, company=company, dimensions=dimensions)

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
        elif self._embedding and cv_summary and job_description:
            embeddings = await self._embedding.embed([cv_summary, job_description])
            semantic_score = self._semantic_scorer.score(embeddings[0], embeddings[1])
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
            job_id=job_id,
            match_id=match_id,
            score=result.overall_score,
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
