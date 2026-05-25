from __future__ import annotations

import uuid as uuid_mod
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.domain.models import CandidateProfile

router = APIRouter(prefix="/profile", tags=["profile"])

_ALLOWED_EXTENSIONS = {".pdf", ".tex"}


class UploadCVRequest(BaseModel):
    tex_content: str
    language: str = "en"


class ProfilePatchRequest(BaseModel):
    name_override: str | None = None
    location_override: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None


@router.post("/upload", response_model=CandidateProfile)
async def upload_cv(
    body: UploadCVRequest,
    service: Annotated[object, Depends(get_profile_service)],
) -> CandidateProfile:
    return await service.parse_and_create(body.tex_content, body.language)


@router.post("/upload-file", response_model=CandidateProfile)
async def upload_file(
    request: Request,
    service: Annotated[object, Depends(get_profile_service)],
    file: UploadFile = File(...),
    language: Literal["en", "es"] = Form("en"),
) -> CandidateProfile:
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
        )
    max_bytes = request.app.state.settings.max_upload_bytes
    if file.size and file.size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_bytes // (1024 * 1024)} MB",
        )
    file_bytes = await file.read()
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_bytes // (1024 * 1024)} MB",
        )
    return await service.parse_file_and_create(file_bytes, filename, language)


@router.get("/list", response_model=list[CandidateProfile])
async def list_profiles(
    service: Annotated[object, Depends(get_profile_service)],
) -> list[CandidateProfile]:
    return await service.list_profiles()


@router.get("/current", response_model=CandidateProfile)
async def get_current_profile(
    service: Annotated[object, Depends(get_profile_service)],
    language: str | None = None,
) -> CandidateProfile:
    profile = await service.get_current_profile(language=language)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile found")
    return profile


@router.get("/{profile_id}", response_model=CandidateProfile)
async def get_profile(
    profile_id: str,
    service: Annotated[object, Depends(get_profile_service)],
) -> CandidateProfile:
    profile = await service.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.patch("/{profile_id}", response_model=CandidateProfile)
async def update_profile(
    profile_id: uuid_mod.UUID,
    body: ProfilePatchRequest,
    service: Annotated[object, Depends(get_profile_service)],
) -> CandidateProfile:
    fields = body.model_dump(exclude_unset=True)
    for key, value in list(fields.items()):
        if key.endswith("_url") and value is not None:
            value = value.strip()
            if value and not (value.startswith("http://") or value.startswith("https://")):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{key} must start with http:// or https://",
                )
            fields[key] = value or None
    try:
        profile = await service.update_profile(profile_id, fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile
