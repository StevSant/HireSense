from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.domain.models import CandidateProfile

router = APIRouter(prefix="/profile", tags=["profile"])


class UploadCVRequest(BaseModel):
    tex_content: str
    language: str = "en"


@router.post("/upload", response_model=CandidateProfile)
async def upload_cv(
    body: UploadCVRequest,
    service: Annotated[object, Depends(get_profile_service)],
) -> CandidateProfile:
    return await service.parse_and_create(body.tex_content, body.language)


@router.get("/{profile_id}", response_model=CandidateProfile)
async def get_profile(
    profile_id: str,
    service: Annotated[object, Depends(get_profile_service)],
) -> CandidateProfile:
    profile = await service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile
