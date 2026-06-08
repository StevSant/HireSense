from __future__ import annotations

import logging
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from hiresense.preference.domain.explanation import PreferenceExplanation, build_explanation
from hiresense.preference.domain.feedback_kind import FeedbackKind
from hiresense.preference.domain.feedback_signal import FeedbackSignal
from hiresense.preference.domain.feedback_source import FeedbackSource
from hiresense.preference.domain.preference_model import PreferenceModel
from hiresense.preference.domain.outcome_observation import OutcomeObservation
from hiresense.preference.domain.signal_contribution import SignalContribution
from hiresense.preference.domain.taste_calculator import TasteVectorCalculator
from hiresense.preference.domain.weight_nudge_calculator import WeightNudgeCalculator

logger = logging.getLogger(__name__)


class PreferenceService:
    def __init__(
        self,
        *,
        repository: Any,
        vector_store: Any,
        calculator: TasteVectorCalculator,
        weights: dict[FeedbackKind, float],
        enabled: bool,
        nudge_calculator: WeightNudgeCalculator | None = None,
        base_weights: dict[str, int] | None = None,
        llm: Any | None = None,
        explanation_enabled: bool = False,
    ) -> None:
        self._repo = repository
        self._vector_store = vector_store
        self._calc = calculator
        self._weights = weights
        self._enabled = enabled
        self._nudge_calc = nudge_calculator
        self._base_weights = dict(base_weights or {})
        self._llm = llm
        self._explanation_enabled = explanation_enabled
        self._job_lookup: Any | None = None
        self._dimension_scorer: Any | None = None

    def attach_job_lookup(self, job_lookup: Any) -> None:
        """Late-bind the job-title lookup used by the LLM explanation summary.
        Two-phase wiring: the ingestion orchestrator is built after the
        preference service, so it is attached once available."""
        self._job_lookup = job_lookup

    def attach_dimension_scorer(self, scorer: Any) -> None:
        """Late-bind the dimension scorer used to snapshot per-job scores.

        Two-phase wiring (mirrors ``attach_job_lookup``): the matching layer is
        built after the preference service, so the scorer — a
        ``DimensionScorerPort`` whose ``score_dimensions(job_id) ->
        dict[str, float] | None`` runs the matching dimension scorers for the
        job times the current profile — is attached once available. When absent
        (or it returns ``None``), recorded signals carry no dimension scores, so
        no observations are produced and ``weight_overrides`` stays empty,
        leaving matching byte-identical to today."""
        self._dimension_scorer = scorer

    async def _record(
        self,
        job_id: uuid_mod.UUID,
        kind: FeedbackKind,
        source: FeedbackSource,
        capture_dimensions: bool = False,
    ) -> FeedbackSignal:
        embedding: list[float] | None = None
        if self._vector_store is not None:
            try:
                embedding = await self._vector_store.get_vector(str(job_id))
            except Exception:
                logger.exception("preference: get_vector failed for %s", job_id)
        if embedding is None:
            logger.debug(
                "preference: no embedding for job %s (not indexed yet?) — "
                "signal stored, no contribution",
                job_id,
            )
        # Outcome (implicit) signals snapshot the matching dimension scores once,
        # at outcome time, off the request path. Failure degrades gracefully:
        # the signal is still stored, simply with no nudging contribution.
        dimension_scores: dict[str, float] | None = None
        if capture_dimensions and self._dimension_scorer is not None:
            try:
                dimension_scores = await self._dimension_scorer.score_dimensions(str(job_id))
            except Exception:
                logger.exception(
                    "preference: dimension-score capture failed for %s — "
                    "signal stored, no nudging contribution",
                    job_id,
                )
                dimension_scores = None
        signal = self._repo.add_signal(
            FeedbackSignal(
                job_id=job_id,
                kind=kind,
                source=source,
                job_embedding=embedding,
                dimension_scores=dimension_scores,
            )
        )
        self._recompute()
        return signal

    async def record_signal(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind
    ) -> FeedbackSignal:
        return await self._record(
            job_id, kind, FeedbackSource.EXPLICIT, capture_dimensions=False
        )

    async def record_implicit_signal(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind
    ) -> FeedbackSignal:
        return await self._record(
            job_id, kind, FeedbackSource.IMPLICIT, capture_dimensions=True
        )

    def query_vector(self, baseline: list[float]) -> list[float]:
        if not self._enabled:
            return baseline
        model = self._repo.get_model()
        if model is None or not model.delta_vector:
            return baseline
        if len(model.delta_vector) != len(baseline):
            return baseline
        return self._calc.blend(baseline, model.delta_vector)

    def weight_overrides(self) -> dict[str, int]:
        """Per-dimension integer weight deltas for the matching composite.

        Empty when disabled, when no model exists, or when the nudge gate is
        unmet — making matching byte-identical to today in all those cases."""
        if not self._enabled:
            return {}
        model = self._repo.get_model()
        if model is None:
            return {}
        return dict(model.weight_overrides)

    def weights_view(self) -> list[dict[str, Any]]:
        """Base + override + effective integer weight per known dimension.

        ``effective = max(0, base + override)`` mirrors the matching composite.
        Dimensions appearing only in overrides (no configured base) are reported
        with a base of 0 so the view never silently drops a learned nudge."""
        overrides = self.weight_overrides()
        names = list(self._base_weights.keys())
        for name in overrides:
            if name not in self._base_weights:
                names.append(name)
        view: list[dict[str, Any]] = []
        for name in names:
            base = int(self._base_weights.get(name, 0))
            delta = int(overrides.get(name, 0))
            view.append(
                {
                    "dimension": name,
                    "base_weight": base,
                    "override": delta,
                    "effective_weight": max(0, base + delta),
                }
            )
        return view

    def list_signals(self) -> list[FeedbackSignal]:
        return self._repo.list_signals()

    async def explain(self) -> PreferenceExplanation:
        model = self._repo.get_model()
        delta = model.delta_vector if model is not None else None
        overrides = dict(model.weight_overrides) if model is not None else {}
        signals = self._repo.list_signals()
        explanation = build_explanation(
            signals, delta_vector=delta, weight_overrides=overrides
        )
        if self._explanation_enabled and self._llm is not None:
            summary = await self._build_summary(signals, explanation)
            if summary:
                explanation = explanation.model_copy(update={"summary": summary})
        return explanation

    async def _build_summary(
        self, signals: list[FeedbackSignal], explanation: PreferenceExplanation
    ) -> str | None:
        try:
            pos_titles = self._titles_for([s for s in signals if s.kind.polarity > 0])
            neg_titles = self._titles_for([s for s in signals if s.kind.polarity < 0])
            if not pos_titles and not neg_titles:
                return None
            # Job titles are untrusted external input (ingested from job boards);
            # they flow into the prompt verbatim. Blast radius is tiny — the output
            # is a cosmetic summary string with no tool access — but treat as such.
            prompt = (
                "Summarize the candidate's evolving job preferences in one or two "
                "short sentences, plain and specific.\n"
                f"Liked/positively-signaled roles: {', '.join(pos_titles) or 'none'}.\n"
                f"Disliked/negatively-signaled roles: {', '.join(neg_titles) or 'none'}.\n"
                f"Total signals: {explanation.total_signals} "
                f"({explanation.positive_count} positive, {explanation.negative_count} negative)."
            )
            system = (
                "You phrase a concise preference drift summary. One or two sentences. "
                "No preamble, no JSON, no bullet points."
            )
            text = await self._llm.complete(prompt, system=system)
            text = (text or "").strip()
            return text or None
        except Exception:
            logger.exception("preference: LLM explanation failed — using deterministic only")
            return None

    def _titles_for(self, signals: list[FeedbackSignal]) -> list[str]:
        if self._job_lookup is None:
            return []
        titles: list[str] = []
        for s in signals:
            try:
                job = self._job_lookup.get_job_by_id(str(s.job_id))
            except Exception:
                job = None
            if job is not None and getattr(job, "title", None):
                titles.append(job.title)
        return titles[:10]

    def reset(self) -> None:
        self._repo.clear()

    def _recompute(self) -> None:
        all_signals = self._repo.list_signals()
        signals = [s for s in all_signals if s.job_embedding]
        overrides = self._compute_overrides(all_signals)
        if not signals:
            # No embedding-bearing signals -> no taste delta. Still persist the
            # overrides if any exist (an outcome signal whose job is unindexed
            # contributes to nudging via its dimension scores, not its vector).
            if overrides:
                self._repo.save_model(
                    PreferenceModel(delta_vector=[], weight_overrides=overrides)
                )
            return
        # Dimension is taken from the first signal's embedding. If the embedding
        # model's width ever changes mid-corpus, compute_delta skips off-width
        # vectors and query_vector's dim guard discards a wrong-width delta — so
        # the worst case is the model going inert until reset, never a bad query.
        dim = len(signals[0].job_embedding)
        now = datetime.now(timezone.utc)
        contributions = [self._to_contribution(s, now) for s in signals]
        delta = self._calc.compute_delta(contributions, dim=dim)
        self._repo.save_model(
            PreferenceModel(delta_vector=delta, weight_overrides=overrides)
        )

    def _compute_overrides(self, signals: list[FeedbackSignal]) -> dict[str, int]:
        # Nudging needs a calculator. Each signal contributes only via the
        # dimension scores snapshotted onto it at record time; signals without
        # them (explicit, or capture-failed) contribute nothing. Absent the
        # calculator, or no signal carries scores, return no overrides ->
        # matching byte-identical to today.
        if self._nudge_calc is None:
            return {}
        observations: list[OutcomeObservation] = []
        for signal in signals:
            scores = signal.dimension_scores
            if not scores:
                continue
            polarity = signal.kind.polarity
            for dimension, score in scores.items():
                observations.append(
                    OutcomeObservation(
                        dimension=dimension,
                        dimension_score=float(score),
                        polarity=polarity,
                    )
                )
        return self._nudge_calc.compute_overrides(observations)

    def _to_contribution(self, signal: FeedbackSignal, now: datetime) -> SignalContribution:
        created = signal.created_at or now
        # SQLite returns naive datetimes even for timezone=True columns.
        # Treat a naive created_at as UTC so the subtraction doesn't crash.
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (now - created).total_seconds() / 86400.0)
        return SignalContribution(
            embedding=signal.job_embedding or [],
            polarity=signal.kind.polarity,
            weight=self._weights.get(signal.kind, 1.0),
            age_days=age_days,
        )
