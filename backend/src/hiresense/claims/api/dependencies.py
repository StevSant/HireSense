from __future__ import annotations

from fastapi import Request

from hiresense.claims.domain import CandidateClaimService


def get_candidate_claim_service(request: Request) -> CandidateClaimService:
    return request.app.state.claims.get_candidate_claim_service()
