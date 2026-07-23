from __future__ import annotations

from fastapi import Request

from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.matching.domain import BatchEvaluationService, MatchingOrchestrator
from hiresense.tracking.domain import TrackingService


def get_matching_orchestrator(request: Request) -> MatchingOrchestrator:
    return request.app.state.matching.get_orchestrator()


def get_batch_evaluation_service(request: Request) -> BatchEvaluationService:
    return request.app.state.matching.get_batch_evaluation_service()


def get_tracking_service_for_matching(request: Request) -> TrackingService:
    return request.app.state.tracking.get_tracking_service()


def get_ingestion_orchestrator_for_matching(request: Request) -> IngestionOrchestrator:
    return request.app.state.ingestion.get_orchestrator()


def get_optional_profile_service(request: Request):
    """Allow lightweight route fixtures without weakening production auth wiring."""
    try:
        return request.app.state.profile.get_profile_service()
    except AttributeError:
        return None
