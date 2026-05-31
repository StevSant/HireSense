from __future__ import annotations

import math

from hiresense.preference.domain.signal_contribution import SignalContribution


class TasteVectorCalculator:
    """Pure Rocchio relevance-feedback math. No I/O — fully deterministic.

    delta = beta * Σ(decay·w·emb | positive) - gamma * Σ(decay·w·emb | negative)
    taste = normalize(alpha·baseline + delta)
    """

    def __init__(self, *, alpha: float, beta: float, gamma: float, tau_days: float) -> None:
        self._alpha = alpha
        self._beta = beta
        self._gamma = gamma
        self._tau_days = tau_days

    def decay(self, age_days: float) -> float:
        if self._tau_days <= 0:
            return 1.0
        return math.exp(-max(0.0, age_days) / self._tau_days)

    def compute_delta(self, contributions: list[SignalContribution], *, dim: int) -> list[float]:
        acc = [0.0] * dim
        for c in contributions:
            if len(c.embedding) != dim:
                continue
            coeff = self.decay(c.age_days) * c.weight
            coeff *= self._beta if c.polarity >= 0 else -self._gamma
            for i in range(dim):
                acc[i] += coeff * c.embedding[i]
        return acc

    def blend(self, baseline: list[float], delta: list[float]) -> list[float]:
        combined = [self._alpha * b + d for b, d in zip(baseline, delta)]
        return self._normalize(combined)

    @staticmethod
    def _normalize(v: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0.0:
            return v
        return [x / norm for x in v]
