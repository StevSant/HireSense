from __future__ import annotations

from dataclasses import dataclass

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.claims.api.provider import ClaimsProvider
from hiresense.claims.domain import CandidateClaimService
from hiresense.claims.infrastructure import CandidateClaimRepository


@dataclass(frozen=True)
class ClaimsBuild:
    provider: ClaimsProvider
    service: CandidateClaimService


def build_claims(infra: SharedInfra) -> ClaimsBuild:
    repository = CandidateClaimRepository(session_factory=infra.sync_session_factory)
    service = CandidateClaimService(repository)
    return ClaimsBuild(provider=ClaimsProvider(service), service=service)
