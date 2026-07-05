from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from hiresense.cover_letter_templates.api.dependencies import get_template_service
from hiresense.cover_letter_templates.api.schemas import (
    CreateCoverLetterTemplateRequest,
    UpdateCoverLetterTemplateRequest,
)
from hiresense.cover_letter_templates.domain.models import CoverLetterTemplate
from hiresense.cover_letter_templates.domain.services import CoverLetterTemplateService
from hiresense.identity.api.dependencies import require_auth

router = APIRouter(
    prefix="/cover-letter-templates",
    tags=["cover-letter-templates"],
    dependencies=[Depends(require_auth)],
)


@router.get("", response_model=list[CoverLetterTemplate])
def list_templates(
    service: CoverLetterTemplateService = Depends(get_template_service),
) -> list[CoverLetterTemplate]:
    return service.list()


@router.post("", response_model=CoverLetterTemplate, status_code=201)
def create_template(
    body: CreateCoverLetterTemplateRequest,
    service: CoverLetterTemplateService = Depends(get_template_service),
) -> CoverLetterTemplate:
    try:
        return service.create(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{template_id}", response_model=CoverLetterTemplate)
def update_template(
    template_id: uuid.UUID,
    body: UpdateCoverLetterTemplateRequest,
    service: CoverLetterTemplateService = Depends(get_template_service),
) -> CoverLetterTemplate:
    try:
        updated = service.update(template_id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return updated


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: uuid.UUID,
    service: CoverLetterTemplateService = Depends(get_template_service),
) -> None:
    if not service.delete(template_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
