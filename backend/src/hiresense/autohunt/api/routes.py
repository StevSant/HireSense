from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from hiresense.autohunt.api.dependencies import get_autohunt_service
from hiresense.autohunt.domain import AutoHuntService, Digest
from hiresense.identity.api.dependencies import enforce_expensive_rate_limit, require_auth

router = APIRouter(prefix="/autohunt", tags=["autohunt"], dependencies=[Depends(require_auth)])


@router.post(
    "/run", response_model=Digest, dependencies=[Depends(enforce_expensive_rate_limit)]
)
async def run(service: AutoHuntService = Depends(get_autohunt_service)) -> Digest:
    return await service.run()


@router.get("/digests", response_model=list[Digest])
def list_digests(
    limit: int = Query(default=20, ge=1, le=100),
    sort: str | None = None,
    service: AutoHuntService = Depends(get_autohunt_service),
) -> list[Digest]:
    return service.list_recent(limit, sort)


@router.get("/digests/latest", response_model=None)
def latest_digest(
    service: AutoHuntService = Depends(get_autohunt_service),
) -> Digest | Response:
    digest = service.latest()
    if digest is None:
        return Response(status_code=204)
    return digest
