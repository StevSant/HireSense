from __future__ import annotations

import uuid

from hiresense.claims.domain.models import CandidateClaim, ClaimVerificationStatus
from hiresense.claims.ports import CandidateClaimRepositoryPort


class CandidateClaimService:
    def __init__(self, repository: CandidateClaimRepositoryPort) -> None:
        self._repository = repository

    def create(self, *, text: str, source: str, provenance: str) -> CandidateClaim:
        return self._repository.create(
            CandidateClaim(text=text, source=source, provenance=provenance)
        )

    def get(self, claim_id: uuid.UUID) -> CandidateClaim:
        claim = self._repository.get_by_id(claim_id)
        if claim is None:
            raise ValueError(f"Candidate claim {claim_id} not found")
        return claim

    def list(self, status: ClaimVerificationStatus | None = None) -> list[CandidateClaim]:
        return self._repository.list_all(status)

    def list_verified_for_readiness(self) -> list[CandidateClaim]:
        """Return only candidate statements explicitly approved for use as evidence."""
        return self._repository.list_verified()

    def update(self, claim_id: uuid.UUID, **fields: object) -> CandidateClaim:
        claim = self.get(claim_id)
        return self._repository.save(claim.model_copy(update=fields))

    def remove(self, claim_id: uuid.UUID) -> None:
        if not self._repository.delete(claim_id):
            raise ValueError(f"Candidate claim {claim_id} not found")
