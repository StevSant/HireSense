from __future__ import annotations

import logging
from typing import Any

from hiresense.matching.domain import DimensionEvaluator

logger = logging.getLogger(__name__)


class MatchingDimensionScorerAdapter:
    """Bootstrap adapter implementing the preference ``DimensionScorerPort``.

    Given a ``job_id``, it fetches the job (via the ingestion job-query service,
    the same get-job seam ``attach_job_lookup`` uses) and the current candidate
    profile (via the profile service), then runs the *same* matching dimension
    scorers the evaluator uses for ``job x profile``, collecting
    ``{result.dimension: result.score}``.

    Returns ``None`` (no nudging contribution, signal still stored) when the
    job, profile, scorers, or LLM are unavailable, or on any exception. Living
    in ``composition/`` keeps the cross-module call (matching + ingestion +
    profile) out of the pure preference domain.
    """

    def __init__(
        self,
        *,
        evaluator: DimensionEvaluator,
        job_lookup: Any,
        profile_service: Any,
    ) -> None:
        self._evaluator = evaluator
        self._job_lookup = job_lookup
        self._profile_service = profile_service

    async def score_dimensions(self, job_id: str) -> dict[str, float] | None:
        try:
            if not self._evaluator.has_dimension_scorers:
                return None
            job = self._job_lookup.get_job_by_id(job_id)
            if job is None:
                return None
            profile = await self._profile_service.get_current_profile()
            # Reuse the evaluator's own evaluate path so the scores match
            # exactly what matching would produce for this job x profile.
            result = await self._evaluator.evaluate(job, profile)
            scores = {d.dimension: float(d.score) for d in result.dimensions}
            return scores or None
        except Exception:
            logger.exception(
                "preference: dimension-score adapter failed for job %s — no nudging contribution",
                job_id,
            )
            return None
