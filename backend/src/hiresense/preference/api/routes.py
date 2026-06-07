from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from hiresense.identity.api.dependencies import require_auth
from hiresense.preference.api.dependencies import get_preference_service
from hiresense.preference.api.schemas import (
    DimensionWeightResponse,
    FeedbackRequest,
    FeedbackSignalResponse,
)
from hiresense.preference.domain import PreferenceService
from hiresense.preference.domain.explanation import PreferenceExplanation

router = APIRouter(prefix="/preference", tags=["preference"], dependencies=[Depends(require_auth)])


@router.post("/feedback", response_model=FeedbackSignalResponse, status_code=201)
async def submit_feedback(
    request: FeedbackRequest,
    service: PreferenceService = Depends(get_preference_service),
) -> FeedbackSignalResponse:
    signal = await service.record_signal(request.job_id, request.kind)
    return FeedbackSignalResponse.model_validate(signal)


@router.get("/signals", response_model=list[FeedbackSignalResponse])
def list_signals(
    service: PreferenceService = Depends(get_preference_service),
) -> list[FeedbackSignalResponse]:
    return [FeedbackSignalResponse.model_validate(s) for s in service.list_signals()]


@router.get("/explain", response_model=PreferenceExplanation)
async def explain(
    service: PreferenceService = Depends(get_preference_service),
) -> PreferenceExplanation:
    return await service.explain()


@router.get("/weights", response_model=list[DimensionWeightResponse])
def weights(
    service: PreferenceService = Depends(get_preference_service),
) -> list[DimensionWeightResponse]:
    return [DimensionWeightResponse.model_validate(w) for w in service.weights_view()]


@router.post("/reset", status_code=204)
def reset(
    service: PreferenceService = Depends(get_preference_service),
) -> Response:
    service.reset()
    return Response(status_code=204)
