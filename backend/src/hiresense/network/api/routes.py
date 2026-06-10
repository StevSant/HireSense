from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from hiresense.identity.api.dependencies import require_auth
from hiresense.network.api.dependencies import get_contacts_repository, get_import_service
from hiresense.network.domain import (
    ConnectionsParseError,
    Contact,
    NetworkImportService,
    normalize_company,
)
from hiresense.network.ports import ContactsRepositoryPort

router = APIRouter(
    prefix="/network",
    tags=["network"],
    dependencies=[Depends(require_auth)],
)

_ALLOWED_EXTENSIONS = {".zip", ".csv"}
_ZIP_MAGIC = b"PK\x03\x04"


class ImportResponse(BaseModel):
    contacts: int
    imported_at: str | None


class ContactsResponse(BaseModel):
    contacts: list[Contact]


class MatchResponse(BaseModel):
    company_normalized: str
    contacts: list[Contact]


def _validate_upload_content(ext: str, file_bytes: bytes) -> None:
    """Cheap content sniffing so the declared extension matches the payload."""
    if ext == ".zip" and not file_bytes.startswith(_ZIP_MAGIC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match the .zip extension",
        )
    if ext == ".csv":
        try:
            file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content is not valid UTF-8 text for a .csv upload",
            ) from exc


@router.post("/import", response_model=ImportResponse)
async def import_connections(
    request: Request,
    service: Annotated[NetworkImportService | None, Depends(get_import_service)],
    file: UploadFile = File(...),
) -> ImportResponse:
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Network module is not available",
        )

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
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_bytes // (1024 * 1024)} MB",
        )

    file_bytes = await file.read()
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large. Maximum size: {max_bytes // (1024 * 1024)} MB",
        )

    _validate_upload_content(ext, file_bytes)

    try:
        count = await service.import_upload(file_bytes, filename=filename)
    except ConnectionsParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    last = await service.last_imported_at()
    return ImportResponse(
        contacts=count,
        imported_at=last.isoformat() if last is not None else None,
    )


@router.get("/contacts", response_model=ContactsResponse)
async def list_contacts(
    repository: Annotated[ContactsRepositoryPort | None, Depends(get_contacts_repository)],
    company: str | None = None,
) -> ContactsResponse:
    if repository is None:
        return ContactsResponse(contacts=[])
    contacts = await asyncio.to_thread(repository.list_all, company)
    return ContactsResponse(contacts=contacts)


@router.get("/match", response_model=MatchResponse)
async def match_contacts(
    repository: Annotated[ContactsRepositoryPort | None, Depends(get_contacts_repository)],
    company: str,
) -> MatchResponse:
    normalized = normalize_company(company)
    if repository is None:
        return MatchResponse(company_normalized=normalized, contacts=[])
    contacts = await asyncio.to_thread(repository.find_by_company, normalized)
    return MatchResponse(company_normalized=normalized, contacts=contacts)
