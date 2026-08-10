from __future__ import annotations

from fastapi import Request

from hiresense.ingestion.domain.job_query_service import JobQueryService
from hiresense.matching.domain import (
    BatchEvaluationService,
    DimensionEvaluator,
    MatchAnalyzer,
)
from hiresense.profile.domain import ProfileService
from hiresense.tracking.domain import TrackingService


def get_dimension_evaluator(request: Request) -> DimensionEvaluator:
    return request.app.state.matching.get_dimension_evaluator()


def get_match_analyzer(request: Request) -> MatchAnalyzer:
    return request.app.state.matching.get_match_analyzer()


def get_batch_evaluation_service(request: Request) -> BatchEvaluationService:
    return request.app.state.matching.get_batch_evaluation_service()


def get_tracking_service_for_matching(request: Request) -> TrackingService:
    return request.app.state.tracking.get_tracking_service()


def get_job_query_for_matching(request: Request) -> JobQueryService:
    return request.app.state.ingestion.get_job_query()


def get_optional_profile_service(request: Request) -> ProfileService | None:
    """Allow lightweight route fixtures without weakening production auth wiring."""
    try:
        return request.app.state.profile.get_profile_service()
    except AttributeError:
        return None
