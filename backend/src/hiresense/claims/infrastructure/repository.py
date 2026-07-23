from __future__ import annotations

import uuid

from sqlalchemy import select

from hiresense.claims.domain.models import CandidateClaim, ClaimVerificationStatus
from hiresense.claims.infrastructure.orm import CandidateClaimOrm
from hiresense.infrastructure import SqlRepository

_CONTENT_FIELDS = ("text", "source", "provenance", "verification_status")


def _to_domain(row: CandidateClaimOrm) -> CandidateClaim:
    return CandidateClaim.model_validate(row)


class CandidateClaimRepository(SqlRepository):
    def get_by_id(self, claim_id: uuid.UUID) -> CandidateClaim | None:
        return self._get_by_pk(CandidateClaimOrm, claim_id, _to_domain)

    def list_all(self, status: ClaimVerificationStatus | None = None) -> list[CandidateClaim]:
        statement = select(CandidateClaimOrm).order_by(
            CandidateClaimOrm.created_at.desc(), CandidateClaimOrm.id
        )
        if status is not None:
            statement = statement.where(CandidateClaimOrm.verification_status == status.value)
        return self._select_all(statement, _to_domain)

    def list_verified(self) -> list[CandidateClaim]:
        return self.list_all(ClaimVerificationStatus.VERIFIED)

    def create(self, claim: CandidateClaim) -> CandidateClaim:
        row = CandidateClaimOrm(
            **{
                field: (
                    getattr(claim, field).value
                    if field == "verification_status"
                    else getattr(claim, field)
                )
                for field in _CONTENT_FIELDS
            }
        )
        return self._insert(row, _to_domain)

    def save(self, claim: CandidateClaim) -> CandidateClaim:
        if claim.id is None:
            return self.create(claim)
        fields = {
            field: (
                getattr(claim, field).value
                if field == "verification_status"
                else getattr(claim, field)
            )
            for field in _CONTENT_FIELDS
        }
        saved = self._update_by_pk(CandidateClaimOrm, claim.id, fields, _to_domain)
        if saved is None:
            raise ValueError(f"Candidate claim {claim.id} not found")
        return saved

    def delete(self, claim_id: uuid.UUID) -> bool:
        return self._delete_by_pk(CandidateClaimOrm, claim_id)
