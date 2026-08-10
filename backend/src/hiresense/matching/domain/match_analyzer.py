from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from hiresense.shared.kernel.events import MatchCompletedEvent
from hiresense.shared.kernel.exceptions import UpstreamUnavailableError
from hiresense.shared.kernel.json_extract import extract_json
from hiresense.shared.kernel.prompt_boundary import PromptBoundary
from hiresense.matching.domain.models import MatchResult, ScoreBreakdown
from hiresense.matching.domain.semantic_scorer import SemanticScorer
from hiresense.matching.domain.skill_matcher import SkillMatcher
from hiresense.shared.ports.llm import LLMTimeoutError

logger = logging.getLogger(__name__)


class MatchAnalyzer:
    """Produces a heuristic MatchResult: semantic + skill + LLM experience and
    language sub-scores, combined through ScoreBreakdown's weights.

    The other half of the former MatchingOrchestrator. This pipeline and
    DimensionEvaluator's dimension fan-out are independent scoring systems that
    happened to share a class; they share no state and never call each other.
    """

    def __init__(
        self,
        llm: Any,
        event_bus: Any,
        embedding: Any | None = None,
        breakdown_weights: dict[str, float] | None = None,
    ) -> None:
        self._llm = llm
        self._event_bus = event_bus
        self._embedding = embedding
        # Percentages for the four heuristic sub-scores, normalized to fractions.
        # None keeps ScoreBreakdown's own defaults, so a bare analyzer (tests,
        # bare apps) scores exactly as before.
        self._breakdown_weights = breakdown_weights
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
            self._get_llm_analysis(job_description, job_skills, cv_summary, cv_skills, cv_text),
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
            overall_score=breakdown.weighted_average(self._breakdown_weights),
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
            f"Job Description: {PromptBoundary.untrusted_job_content(job_description, max_chars=12000)}\n"
            f"Required Skills: {', '.join(job_skills)}\n\n"
            f"Candidate Summary: {cv_summary}\n"
            f"Candidate Skills: {', '.join(cv_skills)}\n\n"
            f"Candidate CV (full text):\n{PromptBoundary.untrusted_cv_content(cv_text or '')}\n\n"
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
                prompt,
                system=(
                    "You are a job matching analysis assistant. "
                    f"{PromptBoundary.untrusted_content_instruction()}"
                ),
            )
        except LLMTimeoutError:
            # Let the timeout surface as a 504 (issue #139) rather than folding it
            # into a generic analysis failure.
            raise
        except Exception as exc:
            # Do NOT fall back to experience_score=0.5 / language_score=0.5 — 0.5
            # is a perfectly plausible score, so the user reads an outage as a
            # genuine mediocre match and it gets persisted as one (issues
            # #147/#142). Raise so the API returns a 503.
            logger.exception("LLM analysis failed")
            raise UpstreamUnavailableError("match analysis failed") from exc

        # Shared kernel parser: tolerates markdown fences and surrounding prose,
        # replacing the private fence regex this module used to carry.
        parsed = extract_json(response)
        if not isinstance(parsed, dict):
            logger.warning(
                "Matching LLM returned non-JSON (first 500 chars): %r",
                response[:500],
            )
            raise UpstreamUnavailableError("match analysis failed")
        return parsed
