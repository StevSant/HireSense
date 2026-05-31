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
from hiresense.preference.domain.signal_contribution import SignalContribution
from hiresense.preference.domain.taste_calculator import TasteVectorCalculator

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
        llm: Any | None = None,
        explanation_enabled: bool = False,
    ) -> None:
        self._repo = repository
        self._vector_store = vector_store
        self._calc = calculator
        self._weights = weights
        self._enabled = enabled
        self._llm = llm
        self._explanation_enabled = explanation_enabled
        self._job_lookup: Any | None = None

    def attach_job_lookup(self, job_lookup: Any) -> None:
        """Late-bind the job-title lookup used by the LLM explanation summary.
        Two-phase wiring: the ingestion orchestrator is built after the
        preference service, so it is attached once available."""
        self._job_lookup = job_lookup

    async def _record(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind, source: FeedbackSource
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
        signal = self._repo.add_signal(
            FeedbackSignal(
                job_id=job_id,
                kind=kind,
                source=source,
                job_embedding=embedding,
            )
        )
        self._recompute()
        return signal

    async def record_signal(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind
    ) -> FeedbackSignal:
        return await self._record(job_id, kind, FeedbackSource.EXPLICIT)

    async def record_implicit_signal(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind
    ) -> FeedbackSignal:
        return await self._record(job_id, kind, FeedbackSource.IMPLICIT)

    def query_vector(self, baseline: list[float]) -> list[float]:
        if not self._enabled:
            return baseline
        model = self._repo.get_model()
        if model is None or not model.delta_vector:
            return baseline
        if len(model.delta_vector) != len(baseline):
            return baseline
        return self._calc.blend(baseline, model.delta_vector)

    def list_signals(self) -> list[FeedbackSignal]:
        return self._repo.list_signals()

    async def explain(self) -> PreferenceExplanation:
        model = self._repo.get_model()
        delta = model.delta_vector if model is not None else None
        signals = self._repo.list_signals()
        explanation = build_explanation(signals, delta_vector=delta)
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
        signals = [s for s in self._repo.list_signals() if s.job_embedding]
        if not signals:
            return
        # Dimension is taken from the first signal's embedding. If the embedding
        # model's width ever changes mid-corpus, compute_delta skips off-width
        # vectors and query_vector's dim guard discards a wrong-width delta — so
        # the worst case is the model going inert until reset, never a bad query.
        dim = len(signals[0].job_embedding)
        now = datetime.now(timezone.utc)
        contributions = [self._to_contribution(s, now) for s in signals]
        delta = self._calc.compute_delta(contributions, dim=dim)
        self._repo.save_model(PreferenceModel(delta_vector=delta))

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
