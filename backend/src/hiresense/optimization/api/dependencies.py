from __future__ import annotations

from fastapi import Request

from hiresense.optimization.domain import CVOptimizer


def get_cv_optimizer(request: Request) -> CVOptimizer:
    return request.app.state.optimization.get_cv_optimizer()
