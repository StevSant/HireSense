from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response

from hiresense.claims.api.dependencies import get_candidate_claim_service
from hiresense.claims.api.schemas import (
    CandidateClaimResponse,
    CreateCandidateClaimRequest,
    UpdateCandidateClaimRequest,
)
from hiresense.claims.domain import CandidateClaimService
from hiresense.claims.domain.models import ClaimVerificationStatus
from hiresense.identity.api.dependencies import require_auth

router = APIRouter(prefix="/claims", tags=["claims"], dependencies=[Depends(require_auth)])


@router.post("", response_model=CandidateClaimResponse, status_code=201)
def create_claim(
    request: CreateCandidateClaimRequest,
    service: CandidateClaimService = Depends(get_candidate_claim_service),
) -> CandidateClaimResponse:
    claim = service.create(text=request.text, source=request.source, provenance=request.provenance)
    return CandidateClaimResponse.model_validate(claim)


@router.get("", response_model=list[CandidateClaimResponse])
def list_claims(
    verification_status: ClaimVerificationStatus | None = None,
    service: CandidateClaimService = Depends(get_candidate_claim_service),
) -> list[CandidateClaimResponse]:
    return [
        CandidateClaimResponse.model_validate(claim) for claim in service.list(verification_status)
    ]


@router.get("/{claim_id}", response_model=CandidateClaimResponse)
def get_claim(
    claim_id: uuid.UUID,
    service: CandidateClaimService = Depends(get_candidate_claim_service),
) -> CandidateClaimResponse:
    try:
        return CandidateClaimResponse.model_validate(service.get(claim_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{claim_id}", response_model=CandidateClaimResponse)
def update_claim(
    claim_id: uuid.UUID,
    request: UpdateCandidateClaimRequest,
    service: CandidateClaimService = Depends(get_candidate_claim_service),
) -> CandidateClaimResponse:
    try:
        claim = service.update(claim_id, **request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CandidateClaimResponse.model_validate(claim)


@router.delete("/{claim_id}", status_code=204)
def delete_claim(
    claim_id: uuid.UUID,
    service: CandidateClaimService = Depends(get_candidate_claim_service),
) -> Response:
    try:
        service.remove(claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
