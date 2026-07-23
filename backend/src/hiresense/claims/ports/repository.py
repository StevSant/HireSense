from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.claims.domain.models import CandidateClaim, ClaimVerificationStatus


class CandidateClaimRepositoryPort(Protocol):
    """Persistence and readiness-read contract for the claims ledger."""

    def get_by_id(self, claim_id: uuid.UUID) -> CandidateClaim | None: ...

    def list_all(self, status: ClaimVerificationStatus | None = None) -> list[CandidateClaim]: ...

    def list_verified(self) -> list[CandidateClaim]: ...

    def create(self, claim: CandidateClaim) -> CandidateClaim: ...

    def save(self, claim: CandidateClaim) -> CandidateClaim: ...

    def delete(self, claim_id: uuid.UUID) -> bool: ...
