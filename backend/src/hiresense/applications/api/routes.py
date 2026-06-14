from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from hiresense.ports import LatexCompileError
from hiresense.applications.api.dependencies import (
    get_application_service,
    get_apply_service,
    get_artifact_service,
)
from hiresense.applications.api.schemas import (
    ApplicationListItemResponse,
    CoverLetterLibraryItem,
    CreateApplicationRequest,
    GenerateCoverLetterRequest,
    GenerateMatchRequest,
    GenerateOptimizationRequest,
    UpdateJobSnapshotRequest,
)
from hiresense.applications.domain.aggregate import (
    ApplicationAggregate,
    CoverLetterView,
    CvOptimizationView,
    InterviewPrepView,
    MatchView,
)
from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.apply_service import ApplyService
from hiresense.applications.domain.artifact_service import ArtifactService
from hiresense.identity.api.dependencies import require_auth
from hiresense.ingestion.api.dependencies import get_ingestion_orchestrator
from hiresense.ingestion.domain.services import IngestionOrchestrator

router = APIRouter(
    prefix="/applications",
    tags=["applications"],
    dependencies=[Depends(require_auth)],
)


# -------- application CRUD --------------------------------------------

@router.get("/cover-letters", response_model=list[CoverLetterLibraryItem])
def list_all_cover_letters(
    service: ApplicationService = Depends(get_application_service),
) -> list[CoverLetterLibraryItem]:
    """Cross-application cover letter library — one row per generated letter."""
    return [CoverLetterLibraryItem(**row) for row in service.list_all_cover_letters()]


@router.post("", response_model=ApplicationAggregate, status_code=201)
async def create_application(
    request: CreateApplicationRequest,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        if request.job_id is not None:
            return await service.create_from_ingested(str(request.job_id))
        return await service.create_from_manual(
            title=request.title or "",
            company=request.company or "",
            description=request.description or "",
            url=request.url,
            notes=request.notes,
        )
    except ValueError as exc:
        msg = str(exc).lower()
        if "not found" in msg:
            status_code = 404
        elif "already tracked" in msg:
            status_code = 409
        else:
            status_code = 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("", response_model=list[ApplicationListItemResponse])
def list_applications(
    service: ApplicationService = Depends(get_application_service),
    orchestrator: IngestionOrchestrator = Depends(get_ingestion_orchestrator),
) -> list[ApplicationListItemResponse]:
    aggregates = service.list()
    return [_to_list_item(a, orchestrator) for a in aggregates]


def _to_list_item(
    a: ApplicationAggregate,
    orchestrator: IngestionOrchestrator,
) -> ApplicationListItemResponse:
    """Shape an aggregate into the list row, enriching pipeline fields
    (location/salary/source/posted) from the linked ingested job when present."""
    location: str | None = None
    salary_range: str | None = None
    source: str | None = None
    posted_date = None
    if a.job_id is not None:
        job = orchestrator.get_job_by_id(str(a.job_id))
        if job is not None:
            location = job.location or None
            salary_range = job.salary_range
            source = job.source
            posted_date = job.posted_date
    return ApplicationListItemResponse(
        id=a.id,
        title=a.title,
        company=a.company,
        status=a.status,
        url=a.url,
        created_at=a.created_at,
        has_match=a.match_count > 0,
        has_optimization=a.optimization_count > 0,
        has_prep=a.interview_prep_count > 0,
        latest_match_score=a.latest_match.overall_score if a.latest_match else None,
        job_id=a.job_id,
        notes=a.notes,
        applied_at=a.applied_at,
        location=location,
        salary_range=salary_range,
        source=source,
        posted_date=posted_date,
    )


@router.get("/{application_id}", response_model=ApplicationAggregate)
def get_application(
    application_id: uuid_mod.UUID,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        return service.get(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{application_id}", status_code=204)
def delete_application(
    application_id: uuid_mod.UUID,
    service: ApplicationService = Depends(get_application_service),
) -> Response:
    try:
        service.remove(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


# -------- job snapshot edits ------------------------------------------

@router.put("/{application_id}/job-snapshot", response_model=ApplicationAggregate)
def update_snapshot(
    application_id: uuid_mod.UUID,
    request: UpdateJobSnapshotRequest,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        return service.update_snapshot(
            application_id,
            description=request.description,
            required_skills=request.required_skills,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{application_id}/job-snapshot/regenerate-skills",
    response_model=ApplicationAggregate,
)
async def regenerate_skills(
    application_id: uuid_mod.UUID,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        return await service.regenerate_skills(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# -------- artifact generation -----------------------------------------

@router.post("/{application_id}/match", response_model=MatchView, status_code=201)
async def generate_match(
    application_id: uuid_mod.UUID,
    request: GenerateMatchRequest,
    service: ArtifactService = Depends(get_artifact_service),
) -> MatchView:
    try:
        return await service.generate_match(application_id, cv_language=request.cv_language)
    except ValueError as exc:
        msg = str(exc).lower()
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{application_id}/optimize", response_model=CvOptimizationView, status_code=201)
async def generate_optimization(
    application_id: uuid_mod.UUID,
    request: GenerateOptimizationRequest,
    service: ArtifactService = Depends(get_artifact_service),
) -> CvOptimizationView:
    try:
        return await service.generate_optimization(
            application_id,
            cv_language=request.cv_language,
            match_id=request.match_id,
        )
    except ValueError as exc:
        msg = str(exc).lower()
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/{application_id}/interview-prep",
    response_model=InterviewPrepView,
    status_code=201,
)
async def generate_interview_prep(
    application_id: uuid_mod.UUID,
    service: ArtifactService = Depends(get_artifact_service),
) -> InterviewPrepView:
    try:
        return await service.generate_interview_prep(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# -------- apply (cover letter + PDFs + bundle + mark-applied) ----------

@router.post(
    "/{application_id}/cover-letter",
    response_model=CoverLetterView,
    status_code=201,
)
async def generate_cover_letter(
    application_id: uuid_mod.UUID,
    request: GenerateCoverLetterRequest,
    service: ApplyService = Depends(get_apply_service),
) -> CoverLetterView:
    try:
        return await service.generate_cover_letter(
            application_id,
            cv_language=request.cv_language,
            tone=request.tone,
        )
    except ValueError as exc:
        msg = str(exc).lower()
        status_code = 404 if "not found" in msg else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except RuntimeError as exc:
        # LLM not configured
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{application_id}/cv.pdf")
async def download_cv_pdf(
    application_id: uuid_mod.UUID,
    optimization_id: uuid_mod.UUID | None = None,
    original: bool = False,
    language: str = "en",
    service: ApplyService = Depends(get_apply_service),
) -> StreamingResponse:
    """Compile a CV PDF for this application.

    Default behaviour returns the latest *optimized* CV. Pass `?original=true`
    to compile the untouched profile CV (in `language`, default `en`), which
    is useful before any optimization has been run.
    """
    try:
        pdf = await service.compile_cv_pdf(
            application_id,
            optimization_id=optimization_id,
            original=original,
            language=language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LatexCompileError as exc:
        raise HTTPException(status_code=500, detail=f"LaTeX compile failed: {exc}") from exc
    suffix = "original" if original else "tailored"
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="cv_{suffix}_{application_id}.pdf"',
        },
    )


@router.get("/{application_id}/cover-letter.pdf")
async def download_cover_letter_pdf(
    application_id: uuid_mod.UUID,
    cover_letter_id: uuid_mod.UUID | None = None,
    service: ApplyService = Depends(get_apply_service),
) -> StreamingResponse:
    try:
        pdf = await service.compile_cover_letter_pdf(application_id, cover_letter_id=cover_letter_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LatexCompileError as exc:
        raise HTTPException(status_code=500, detail=f"LaTeX compile failed: {exc}") from exc
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cover_letter_{application_id}.pdf"'},
    )


@router.get("/{application_id}/bundle.zip")
async def download_bundle(
    application_id: uuid_mod.UUID,
    service: ApplyService = Depends(get_apply_service),
) -> StreamingResponse:
    try:
        zip_bytes = await service.build_bundle(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LatexCompileError as exc:
        raise HTTPException(status_code=500, detail=f"LaTeX compile failed: {exc}") from exc
    return StreamingResponse(
        iter([zip_bytes]),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="application_{application_id}.zip"'},
    )


@router.post("/{application_id}/mark-applied", response_model=ApplicationAggregate)
async def mark_applied(
    application_id: uuid_mod.UUID,
    apply_service: ApplyService = Depends(get_apply_service),
    app_service: ApplicationService = Depends(get_application_service),
) -> ApplicationAggregate:
    try:
        await apply_service.mark_applied(application_id)
        return app_service.get(application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
