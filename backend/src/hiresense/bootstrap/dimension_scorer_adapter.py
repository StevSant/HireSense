from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MatchingDimensionScorerAdapter:
    """Bootstrap adapter implementing the preference ``DimensionScorerPort``.

    Given a ``job_id``, it fetches the job (via the ingestion orchestrator, the
    same get-job seam ``attach_job_lookup`` uses) and the current candidate
    profile (via the profile service), then runs the *same* matching dimension
    scorers the orchestrator uses for ``job x profile``, collecting
    ``{result.dimension: result.score}``.

    Returns ``None`` (no nudging contribution, signal still stored) when the
    job, profile, scorers, or LLM are unavailable, or on any exception. Living
    in ``bootstrap/`` keeps the cross-module call (matching + ingestion +
    profile) out of the pure preference domain.
    """

    def __init__(
        self,
        *,
        orchestrator: Any,
        job_lookup: Any,
        profile_service: Any,
    ) -> None:
        self._orchestrator = orchestrator
        self._job_lookup = job_lookup
        self._profile_service = profile_service

    async def score_dimensions(self, job_id: str) -> dict[str, float] | None:
        try:
            scorers = getattr(self._orchestrator, "_dimension_scorers", None)
            if not scorers:
                return None
            job = self._job_lookup.get_job_by_id(job_id)
            if job is None:
                return None
            profile = await self._profile_service.get_current_profile()
            # Reuse the orchestrator's own evaluate path so the scores match
            # exactly what matching would produce for this job x profile.
            result = await self._orchestrator.evaluate(job, profile)
            scores = {d.dimension: float(d.score) for d in result.dimensions}
            return scores or None
        except Exception:
            logger.exception(
                "preference: dimension-score adapter failed for job %s — no nudging contribution",
                job_id,
            )
            return None
