from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Response

from hiresense.identity.api.dependencies import require_auth
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.schemas import (
    CreateApplicationRequest,
    TrackedApplicationResponse,
    UpdateApplicationRequest,
)
from hiresense.tracking.domain.models import ApplicationStatus
from hiresense.tracking.domain.services import TrackingService

router = APIRouter(prefix="/tracking", tags=["tracking"], dependencies=[Depends(require_auth)])


@router.post("", response_model=TrackedApplicationResponse, status_code=201)
def create_application(
    request: CreateApplicationRequest,
    service: TrackingService = Depends(get_tracking_service),
) -> TrackedApplicationResponse:
    try:
        if request.job_id is not None:
            app = service.track_from_ingestion(str(request.job_id))
        else:
            if request.title is None or request.company is None:
                raise HTTPException(status_code=422, detail="title and company are required")
            app = service.track_job(
                title=request.title,
                company=request.company,
                url=request.url,
                notes=request.notes,
            )
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if "already tracked" in msg:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TrackedApplicationResponse.model_validate(app)


@router.get("", response_model=list[TrackedApplicationResponse])
def list_applications(
    status: ApplicationStatus | None = None,
    service: TrackingService = Depends(get_tracking_service),
) -> list[TrackedApplicationResponse]:
    apps = service.list(status=status)
    return [TrackedApplicationResponse.model_validate(a) for a in apps]


@router.get("/{id}", response_model=TrackedApplicationResponse)
def get_application(
    id: uuid_mod.UUID,
    service: TrackingService = Depends(get_tracking_service),
) -> TrackedApplicationResponse:
    try:
        app = service.get(id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TrackedApplicationResponse.model_validate(app)


@router.patch("/{id}", response_model=TrackedApplicationResponse)
def update_application(
    id: uuid_mod.UUID,
    request: UpdateApplicationRequest,
    service: TrackingService = Depends(get_tracking_service),
) -> TrackedApplicationResponse:
    try:
        if request.status is not None:
            app = service.update_status(id, request.status, notes=request.notes)
        elif request.notes is not None:
            app = service.update_notes(id, request.notes)
        else:
            app = service.get(id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TrackedApplicationResponse.model_validate(app)


@router.delete("/{id}", status_code=204)
def delete_application(
    id: uuid_mod.UUID,
    service: TrackingService = Depends(get_tracking_service),
) -> Response:
    try:
        service.remove(id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
