from __future__ import annotations

import asyncio
import logging
from typing import Any

from opentelemetry import trace

from hiresense.shared.kernel.exceptions import UpstreamUnavailableError
from hiresense.matching.domain.eligibility import (
    EligibilityStatus,
    determine_work_authorization_eligibility,
)
from hiresense.matching.domain.evaluation_result import EvaluationResult
from hiresense.matching.domain.scorers.base import DimensionResult
from hiresense.shared.observability import get_domain_metrics, get_tracer

logger = logging.getLogger(__name__)
_tracer = get_tracer("hiresense.matching")


class DimensionEvaluator:
    """Scores a job x profile across the six weighted LLM dimensions.

    One of the two halves of the former MatchingOrchestrator. That class held
    two disjoint pipelines — this dimension fan-out and the heuristic
    breakdown analysis now in MatchAnalyzer — which shared no instance
    attribute and never called each other.
    """

    def __init__(
        self,
        dimension_scorers: list[Any] | None = None,
        preference: Any | None = None,
        combined_scorer: Any | None = None,
    ) -> None:
        self._dimension_scorers = dimension_scorers or []
        # Optional, duck-typed preference port: exposes weight_overrides() ->
        # {dimension: int delta}. None (or no overrides) => composite is computed
        # exactly as before, so scoring/ranking are byte-identical to today.
        self._preference = preference
        # Optional CombinedDimensionScorer: scores all 6 dimensions in one LLM
        # call instead of fanning out to `dimension_scorers`. It is the default
        # path when set and no explicit `dimension_scorers` override is passed
        # to evaluate(); any failure falls back to the per-scorer fan-out.
        self._combined_scorer = combined_scorer

    @property
    def has_dimension_scorers(self) -> bool:
        """Whether any per-dimension scorer is wired.

        Public because the preference nudge adapter must answer exactly this
        before evaluating. It previously reached in for the private
        `_dimension_scorers` attribute with getattr and a None default, so
        renaming the field would have silently disabled preference nudging
        rather than failing.
        """
        return bool(self._dimension_scorers)

    async def evaluate(
        self, job: Any, profile: Any | None = None, dimension_scorers: list[Any] | None = None
    ) -> EvaluationResult:
        _metrics = get_domain_metrics()
        with _tracer.start_as_current_span("matching.score") as span:
            try:
                title = job.get("title", "") if isinstance(job, dict) else getattr(job, "title", "")
                company = (
                    job.get("company", "") if isinstance(job, dict) else getattr(job, "company", "")
                )
                eligibility = determine_work_authorization_eligibility(job, profile)
                span.set_attribute("matching.eligibility", eligibility.status.value)
                if eligibility.status is EligibilityStatus.INELIGIBLE:
                    result = EvaluationResult(
                        composite_score=0.0,
                        job_title=title,
                        company=company,
                        dimensions=[],
                        eligibility=eligibility,
                    )
                    _metrics.matches_completed_total.add(1)
                    _metrics.match_score.record(0.0)
                    span.set_attribute("matching.score", 0.0)
                    return result

                if dimension_scorers is not None:
                    # Explicit override (e.g. the preference nudge adapter):
                    # always the per-scorer fan-out, bypassing the combined path.
                    dimensions = await self._fan_out(job, profile, dimension_scorers)
                else:
                    dimensions = await self._score_dimensions(job, profile)
                overrides = self._weight_overrides()
                effective = {d.dimension: self._effective_weight(d, overrides) for d in dimensions}
                total_weight = sum(effective.values())
                composite = (
                    sum(d.score * effective[d.dimension] for d in dimensions) / total_weight
                    if total_weight > 0
                    else 0.5
                )

                result = EvaluationResult(
                    composite_score=round(composite, 4),
                    job_title=title,
                    company=company,
                    dimensions=dimensions,
                    eligibility=eligibility,
                )
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

    async def _score_dimensions(self, job: Any, profile: Any | None) -> list[DimensionResult]:
        # Default path: one combined LLM call scoring all 6 dimensions at
        # once. Falls back to the per-scorer fan-out on any failure (no
        # combined scorer wired, the call raising, or an unparseable /
        # incomplete response) so matching degrades gracefully rather than
        # losing dimensions.
        if self._combined_scorer is not None:
            combined = await self._safe_combined_score(self._combined_scorer, job, profile)
            if combined is not None:
                return combined
        return await self._fan_out(job, profile, self._dimension_scorers)

    async def _safe_combined_score(
        self, combined_scorer: Any, job: Any, profile: Any | None
    ) -> list[DimensionResult] | None:
        try:
            results = await combined_scorer.score_all(job, profile)
        except Exception:
            logger.exception(
                "matching: combined dimension scorer raised — falling back to per-dimension scorers"
            )
            return None
        if results is None:
            logger.warning(
                "matching: combined dimension scorer returned no usable result — "
                "falling back to per-dimension scorers"
            )
            return None
        return self._apply_wired_weights(results)

    def _apply_wired_weights(self, results: list[DimensionResult]) -> list[DimensionResult]:
        # The combined scorer doesn't know configured weights (that's wiring
        # concern, not LLM output) — each dimension keeps the weight from the
        # wired per-dimension scorer of the same name, exactly like the fan-out.
        weight_by_dimension = {s.dimension_name: s.weight for s in self._dimension_scorers}
        return [
            result.model_copy(update={"weight": weight_by_dimension[result.dimension]})
            if result.dimension in weight_by_dimension
            else result
            for result in results
        ]

    async def _fan_out(
        self, job: Any, profile: Any | None, scorers: list[Any]
    ) -> list[DimensionResult]:
        async def safe_score(scorer: Any) -> DimensionResult | None:
            try:
                return await scorer.score(job, profile)
            except Exception:
                # A failed dimension used to be reported as score=0.5 at its full
                # weight and with no log line, so a composite could be half
                # invented without leaving a trace. Log it and drop the dimension
                # instead: the composite is renormalized over the dimensions that
                # actually scored (total_weight in evaluate() only sums what is
                # returned here), and the response no longer shows a fabricated
                # mid-range score as if the scorer had produced it.
                logger.exception(
                    "matching: dimension scorer %r failed — excluded from the composite",
                    getattr(scorer, "dimension_name", scorer),
                )
                return None

        results = await asyncio.gather(*[safe_score(s) for s in scorers])
        scored = [result for result in results if result is not None]
        if scorers and not scored:
            # Every wired scorer failed. There is nothing left to average, and
            # evaluate()'s `total_weight == 0` branch would hand back a plausible
            # 0.5 composite built from nothing at all.
            raise UpstreamUnavailableError("all dimension scorers failed")
        return scored
