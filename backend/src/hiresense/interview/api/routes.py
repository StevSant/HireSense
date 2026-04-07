from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Response

from hiresense.identity.api.dependencies import require_auth
from hiresense.interview.api.dependencies import get_interview_prep_service, get_story_service
from hiresense.interview.api.schemas import (
    CreateStoryRequest,
    InterviewPrepResponse,
    PrepareRequest,
    StoryMatchResponse,
    StoryResponse,
    UpdateStoryRequest,
)
from hiresense.interview.domain.models import Competency
from hiresense.interview.domain.services import InterviewPrepService, StoryService

router = APIRouter(prefix="/interview", tags=["interview"], dependencies=[Depends(require_auth)])


@router.post("/stories", response_model=StoryResponse, status_code=201)
def create_story(
    request: CreateStoryRequest,
    service: StoryService = Depends(get_story_service),
) -> StoryResponse:
    try:
        competency = Competency(request.competency)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid competency: {request.competency}") from exc
    story = service.add_story(
        title=request.title,
        competency=competency,
        situation=request.situation,
        task=request.task,
        action=request.action,
        result=request.result,
        reflection=request.reflection,
        tags=request.tags,
    )
    return StoryResponse.model_validate(story)


@router.get("/stories", response_model=list[StoryResponse])
def list_stories(
    competency: str | None = None,
    service: StoryService = Depends(get_story_service),
) -> list[StoryResponse]:
    competency_enum: Competency | None = None
    if competency is not None:
        try:
            competency_enum = Competency(competency)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid competency: {competency}") from exc
    stories = service.list(competency=competency_enum)
    return [StoryResponse.model_validate(s) for s in stories]


@router.get("/stories/{id}", response_model=StoryResponse)
def get_story(
    id: uuid_mod.UUID,
    service: StoryService = Depends(get_story_service),
) -> StoryResponse:
    try:
        story = service.get(id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StoryResponse.model_validate(story)


@router.patch("/stories/{id}", response_model=StoryResponse)
def update_story(
    id: uuid_mod.UUID,
    request: UpdateStoryRequest,
    service: StoryService = Depends(get_story_service),
) -> StoryResponse:
    fields = {k: v for k, v in request.model_dump().items() if v is not None}
    try:
        story = service.update(id, **fields)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return StoryResponse.model_validate(story)


@router.delete("/stories/{id}", status_code=204)
def delete_story(
    id: uuid_mod.UUID,
    service: StoryService = Depends(get_story_service),
) -> Response:
    try:
        service.remove(id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/prepare", response_model=InterviewPrepResponse)
async def prepare_interview(
    request: PrepareRequest,
    service: InterviewPrepService = Depends(get_interview_prep_service),
) -> InterviewPrepResponse:
    job = request.model_dump()
    # Rename job_title -> title for the service
    job["title"] = job.pop("job_title")
    prep = await service.prepare(job)
    return InterviewPrepResponse(
        job_title=prep.job_title,
        company=prep.company,
        matched_stories=[
            StoryMatchResponse(
                story_id=m.story_id,
                story_title=m.story_title,
                relevance=m.relevance,
            )
            for m in prep.matched_stories
        ],
        competencies_to_probe=prep.competencies_to_probe,
        technical_topics=prep.technical_topics,
        negotiation_points=prep.negotiation_points,
    )
