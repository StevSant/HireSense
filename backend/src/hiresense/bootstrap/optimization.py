from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hiresense.optimization.api.provider import OptimizationProvider
from hiresense.optimization.domain import CVOptimizer


@dataclass(frozen=True)
class OptimizationBuild:
    provider: OptimizationProvider
    cv_optimizer: CVOptimizer


def build_optimization(tracked: Callable[[str], Any]) -> OptimizationBuild:
    cv_optimizer = CVOptimizer(llm=tracked("cv_optimizer"))
    provider = OptimizationProvider(cv_optimizer=cv_optimizer)
    return OptimizationBuild(provider=provider, cv_optimizer=cv_optimizer)
