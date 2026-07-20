from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Response

from hiresense.identity.api.dependencies import require_auth
from hiresense.ingestion.api.dependencies import get_ingestion_orchestrator
from hiresense.ingestion.domain.services import IngestionOrchestrator
from hiresense.tracking.api.dependencies import get_tracking_service
from hiresense.tracking.api.schemas import (
    CreateApplicationRequest,
    TrackedApplicationResponse,
    UpdateApplicationRequest,
)
from hiresense.tracking.domain import InvalidStatusTransitionError
from hiresense.tracking.domain.models import ApplicationStatus, TrackedApplication
from hiresense.tracking.domain.services import TrackingService

router = APIRouter(prefix="/tracking", tags=["tracking"], dependencies=[Depends(require_auth)])


def _enrich(
    app: TrackedApplication,
    orchestrator: IngestionOrchestrator,
) -> TrackedApplicationResponse:
    response = TrackedApplicationResponse.model_validate(app)
    if app.job_id is None:
        return response
    job = orchestrator.get_job_by_id(str(app.job_id))
    if job is None:
        return response
    return response.model_copy(
        update={
            "location": job.location or None,
            "salary_range": job.salary_range,
            "source": job.source,
            "posted_date": job.posted_date,
        }
    )


@router.post("", response_model=TrackedApplicationResponse, status_code=201)
def create_application(
    request: CreateApplicationRequest,
    service: TrackingService = Depends(get_tracking_service),
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
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
    return _enrich(app, orchestrator)


@router.get("", response_model=list[TrackedApplicationResponse])
def list_applications(
    status: ApplicationStatus | None = None,
    service: TrackingService = Depends(get_tracking_service),
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
) -> list[TrackedApplicationResponse]:
    apps = service.list(status=status)
    return [_enrich(a, orchestrator) for a in apps]


@router.get("/{id}", response_model=TrackedApplicationResponse)
def get_application(
    id: uuid_mod.UUID,
    service: TrackingService = Depends(get_tracking_service),
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
) -> TrackedApplicationResponse:
    try:
        app = service.get(id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _enrich(app, orchestrator)


@router.patch("/{id}", response_model=TrackedApplicationResponse)
async def update_application(
    id: uuid_mod.UUID,
    request: UpdateApplicationRequest,
    service: TrackingService = Depends(get_tracking_service),
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
) -> TrackedApplicationResponse:
    try:
        if request.status is not None:
            app = await service.update_status(id, request.status, notes=request.notes)
        elif request.notes is not None:
            app = service.update_notes(id, request.notes)
        else:
            app = service.get(id)
    except InvalidStatusTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _enrich(app, orchestrator)


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
