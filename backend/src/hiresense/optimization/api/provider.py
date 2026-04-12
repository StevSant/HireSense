from __future__ import annotations

from hiresense.optimization.domain import CVOptimizer


class OptimizationProvider:
    def __init__(self, cv_optimizer: CVOptimizer) -> None:
        self._cv_optimizer = cv_optimizer

    def get_cv_optimizer(self) -> CVOptimizer:
        return self._cv_optimizer
