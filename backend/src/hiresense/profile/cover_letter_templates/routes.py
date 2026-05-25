from __future__ import annotations

import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Response, status

from hiresense.profile.cover_letter_templates.create_request import (
    CreateCoverLetterTemplateRequest,
)
from hiresense.profile.cover_letter_templates.dependencies import (
    get_cover_letter_template_service,
)
from hiresense.profile.cover_letter_templates.service import CoverLetterTemplateService
from hiresense.profile.cover_letter_templates.update_request import (
    UpdateCoverLetterTemplateRequest,
)
from hiresense.profile.cover_letter_templates.view import CoverLetterTemplateView

router = APIRouter(
    prefix="/profile/cover-letter-templates",
    tags=["cover-letter-templates"],
)


@router.get("", response_model=list[CoverLetterTemplateView])
def list_templates(
    service: CoverLetterTemplateService = Depends(get_cover_letter_template_service),
) -> list[CoverLetterTemplateView]:
    return service.list()


@router.post("", response_model=CoverLetterTemplateView, status_code=status.HTTP_201_CREATED)
def create_template(
    body: CreateCoverLetterTemplateRequest,
    service: CoverLetterTemplateService = Depends(get_cover_letter_template_service),
) -> CoverLetterTemplateView:
    try:
        return service.create(
            name=body.name,
            body=body.body,
            tone=body.tone,
            language=body.language,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@router.patch("/{template_id}", response_model=CoverLetterTemplateView)
def update_template(
    template_id: uuid_mod.UUID,
    body: UpdateCoverLetterTemplateRequest,
    service: CoverLetterTemplateService = Depends(get_cover_letter_template_service),
) -> CoverLetterTemplateView:
    fields = body.model_dump(exclude_unset=True)
    try:
        result = service.update(template_id, fields)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
    return result


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: uuid_mod.UUID,
    service: CoverLetterTemplateService = Depends(get_cover_letter_template_service),
) -> Response:
    if not service.delete(template_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
