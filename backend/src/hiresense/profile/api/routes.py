from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_auth
from hiresense.ports import LatexCompileError
from hiresense.profile.api.dependencies import get_profile_service
from hiresense.profile.domain.apply_profile import ApplyProfile
from hiresense.profile.domain.models import CandidateProfile

router = APIRouter(prefix="/profile", tags=["profile"], dependencies=[Depends(require_auth)])

_ALLOWED_EXTENSIONS = {".pdf", ".tex"}


def _validate_upload_content(ext: str, file_bytes: bytes) -> None:
    """Cheap content sniffing so the declared extension matches the payload.

    A `.tex` upload flows into the LaTeX pipeline, so a binary blob renamed to
    .tex (or a TeX file renamed to .pdf) is rejected up front instead of
    failing deeper in parsing/compilation.
    """
    if ext == ".pdf" and not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match the .pdf extension",
        )
    if ext == ".tex":
        try:
            file_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content is not valid UTF-8 text for a .tex upload",
            ) from exc


class UploadCVRequest(BaseModel):
    tex_content: str
    language: str = "en"


class TranslateRequest(BaseModel):
    target_language: Literal["en", "es"]


class TranslateResponse(BaseModel):
    profile: CandidateProfile
    pdf_ok: bool
    compile_error: str | None = None


class ProfileManualFieldsRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
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
    _validate_upload_content(ext, file_bytes)
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


@router.put("/apply-profile", response_model=CandidateProfile)
async def set_apply_profile(
    body: ApplyProfile,
    service: Annotated[object, Depends(get_profile_service)],
) -> CandidateProfile:
    """Store the one-per-person Apply Assist answer bank. Requires an existing
    profile (404 if the user hasn't created one yet)."""
    updated = await service.set_apply_profile(body)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile found")
    return updated


@router.get("/prefill")
async def get_prefill(
    service: Annotated[object, Depends(get_profile_service)],
    language: str | None = None,
) -> dict[str, object]:
    """Canonical application-form field values for the current profile (the Apply
    Assist autofill handoff bundle). 404 if the user has no profile yet."""
    prefill = await service.get_prefill(language=language)
    if prefill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile found")
    return prefill


@router.post("/translate", response_model=TranslateResponse)
async def translate_cv(
    body: TranslateRequest,
    service: Annotated[object, Depends(get_profile_service)],
) -> TranslateResponse:
    try:
        outcome = await service.translate_to(body.target_language)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return TranslateResponse(
        profile=outcome.profile,
        pdf_ok=outcome.pdf_ok,
        compile_error=outcome.compile_error,
    )


@router.get("/cv.pdf")
async def download_cv_pdf(
    service: Annotated[object, Depends(get_profile_service)],
    language: Literal["en", "es"] = "en",
) -> StreamingResponse:
    try:
        pdf = await service.compile_pdf(language)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except LatexCompileError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LaTeX compile failed: {exc}",
        ) from exc
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cv_{language}.pdf"'},
    )


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
async def update_manual_fields(
    profile_id: str,
    body: ProfileManualFieldsRequest,
    service: Annotated[object, Depends(get_profile_service)],
) -> CandidateProfile:
    updated = await service.update_manual_fields(
        profile_id, body.model_dump(exclude_unset=True)
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return updated
