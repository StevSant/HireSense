from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import Any

from opentelemetry import trace
from pydantic import BaseModel

from hiresense.kernel.events import MatchCompletedEvent
from hiresense.matching.domain.models import MatchResult, ScoreBreakdown
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.matching.domain.semantic_scorer import SemanticScorer
from hiresense.matching.domain.skill_matcher import SkillMatcher
from hiresense.observability import get_domain_metrics, get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer("hiresense.matching")

_MARKDOWN_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def _strip_markdown_fence(text: str) -> str:
    match = _MARKDOWN_FENCE_RE.search(text)
    return match.group(1).strip() if match else text.strip()


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
        preference: Any | None = None,
    ) -> None:
        self._llm = llm
        self._event_bus = event_bus
        self._dimension_scorers = dimension_scorers or []
        self._embedding = embedding
        # Optional, duck-typed preference port: exposes weight_overrides() ->
        # {dimension: int delta}. None (or no overrides) => composite is computed
        # exactly as before, so scoring/ranking are byte-identical to today.
        self._preference = preference
        self._semantic_scorer = SemanticScorer()
        self._skill_matcher = SkillMatcher()

    async def evaluate(self, job: Any, profile: Any | None = None, dimension_scorers: list[Any] | None = None) -> EvaluationResult:
        _metrics = get_domain_metrics()
        with _tracer.start_as_current_span("matching.score") as span:
            try:
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
                overrides = self._weight_overrides()
                effective = {d.dimension: self._effective_weight(d, overrides) for d in dimensions}
                total_weight = sum(effective.values())
                composite = (
                    sum(d.score * effective[d.dimension] for d in dimensions) / total_weight
                    if total_weight > 0
                    else 0.5
                )

                result = EvaluationResult(composite_score=round(composite, 4), job_title=title, company=company, dimensions=dimensions)
                _metrics.matches_completed_total.add(1)
                # composite_score is already 0..1
                span.set_attribute("matching.score", float(result.composite_score))
                _metrics.match_score.record(float(result.composite_score))
                return result
            except Exception:
                span.set_status(trace.Status(trace.StatusCode.ERROR))
                raise

    def _weight_overrides(self) -> dict[str, int]:
        # Read learned per-dimension weight deltas from the optional preference
        # port. Any failure (or no port) yields no overrides, so the composite
        # falls back to base weights and stays identical to today's behavior.
        if self._preference is None:
            return {}
        try:
            return self._preference.weight_overrides() or {}
        except Exception:
            logger.exception("matching: weight_overrides lookup failed — using base weights")
            return {}

    @staticmethod
    def _effective_weight(dimension: DimensionResult, overrides: dict[str, int]) -> int:
        # clamp(base + delta) with a floor of 0: a learned nudge can lower a
        # dimension to zero influence but never make it negative. With no delta
        # for this dimension the base weight is returned unchanged.
        delta = overrides.get(dimension.dimension, 0)
        if delta == 0:
            return dimension.weight
        return max(0, dimension.weight + delta)

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
        cv_text: str | None = None,
    ) -> MatchResult:
        # 1. Semantic score
        async def semantic() -> float:
            if cv_embedding and job_embedding:
                return self._semantic_scorer.score(cv_embedding, job_embedding)
            if self._embedding and cv_summary and job_description:
                embeddings = await self._embedding.embed([cv_summary, job_description])
                return self._semantic_scorer.score(embeddings[0], embeddings[1])
            return 0.0

        # 2. LLM analysis for experience, language, pros/cons, and a verdict on
        # which required skills the candidate demonstrably has (present_skills).
        # Independent of the semantic score, so both run concurrently.
        semantic_score, llm_analysis = await asyncio.gather(
            semantic(),
            self._get_llm_analysis(
                job_description, job_skills, cv_summary, cv_skills, cv_text
            ),
        )

        # 3. Skill match. A required skill counts as matched when it is in the
        # explicit list, appears (word-boundary) in the CV text/summary, or the
        # LLM judged it present from the experience — covering prose-described
        # skills that aren't tagged in the skills list.
        evidence = "\n".join(filter(None, [cv_summary, cv_text]))
        skill_result = self._skill_matcher.match(
            cv_skills,
            job_skills,
            evidence_text=evidence,
            inferred_present=llm_analysis.get("present_skills") or [],
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
        cv_text: str | None = None,
    ) -> dict[str, Any]:
        prompt = (
            "Analyze this job-candidate match.\n\n"
            f"Job Description: {job_description}\n"
            f"Required Skills: {', '.join(job_skills)}\n\n"
            f"Candidate Summary: {cv_summary}\n"
            f"Candidate Skills: {', '.join(cv_skills)}\n\n"
            f"Candidate CV (full text):\n{cv_text or ''}\n\n"
            "Return a JSON object with:\n"
            '- "experience_score": float 0-1\n'
            '- "language_score": float 0-1\n'
            '- "present_skills": from the Required Skills list, the exact items the\n'
            "  candidate demonstrably has based on their skills, summary, or CV text\n"
            "  (include skills evidenced by experience even if not explicitly listed;\n"
            "  use the exact required-skill wording; omit any not clearly supported)\n"
            '- "pros": list of strings\n'
            '- "cons": list of strings\n'
            '- "recommendations": list of strings\n'
            "Return ONLY valid JSON."
        )
        try:
            response = await self._llm.complete(
                prompt, system="You are a job matching analysis assistant."
            )
            cleaned = _strip_markdown_fence(response)
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "Matching LLM returned non-JSON (first 500 chars): %r",
                (cleaned if "cleaned" in locals() else response)[:500],
            )
        except Exception:
            logger.exception("LLM analysis failed")
        return {
            "experience_score": 0.5,
            "language_score": 0.5,
            "present_skills": [],
            "pros": [],
            "cons": [],
            "recommendations": [],
        }
