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
    ) -> None:
        self._repo = repository
        self._vector_store = vector_store
        self._calc = calculator
        self._weights = weights
        self._enabled = enabled

    async def record_signal(
        self, job_id: uuid_mod.UUID, kind: FeedbackKind
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
                source=FeedbackSource.EXPLICIT,
                job_embedding=embedding,
            )
        )
        self._recompute()
        return signal

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

    def explain(self) -> PreferenceExplanation:
        model = self._repo.get_model()
        delta = model.delta_vector if model is not None else None
        return build_explanation(self._repo.list_signals(), delta_vector=delta)

    def reset(self) -> None:
        self._repo.clear()

    def _recompute(self) -> None:
        signals = [s for s in self._repo.list_signals() if s.job_embedding]
        if not signals:
            return
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
