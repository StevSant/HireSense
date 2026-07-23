from __future__ import annotations

import uuid

from hiresense.claims.domain.models import CandidateClaim, ClaimVerificationStatus
from hiresense.claims.domain.service import CandidateClaimService


class InMemoryClaimsRepository:
    def __init__(self) -> None:
        self.claims: dict[uuid.UUID, CandidateClaim] = {}

    def get_by_id(self, claim_id: uuid.UUID) -> CandidateClaim | None:
        return self.claims.get(claim_id)

    def list_all(self, status: ClaimVerificationStatus | None = None) -> list[CandidateClaim]:
        claims = list(self.claims.values())
        return (
            [claim for claim in claims if claim.verification_status == status] if status else claims
        )

    def list_verified(self) -> list[CandidateClaim]:
        return self.list_all(ClaimVerificationStatus.VERIFIED)

    def create(self, claim: CandidateClaim) -> CandidateClaim:
        persisted = claim.model_copy(update={"id": uuid.uuid4()})
        self.claims[persisted.id] = persisted
        return persisted

    def save(self, claim: CandidateClaim) -> CandidateClaim:
        self.claims[claim.id] = claim
        return claim

    def delete(self, claim_id: uuid.UUID) -> bool:
        return self.claims.pop(claim_id, None) is not None


def test_new_candidate_claim_is_unverified_and_excluded_from_readiness_evidence() -> None:
    repository = InMemoryClaimsRepository()
    service = CandidateClaimService(repository)

    claim = service.create(
        text="Reduced batch processing time by 40%.",
        source="resume",
        provenance="Experience section, Acme role",
    )

    assert claim.verification_status is ClaimVerificationStatus.UNVERIFIED
    assert service.list_verified_for_readiness() == []


def test_verified_candidate_claim_is_available_to_readiness_with_its_provenance() -> None:
    repository = InMemoryClaimsRepository()
    service = CandidateClaimService(repository)
    claim = service.create(
        text="Reduced batch processing time by 40%.",
        source="portfolio",
        provenance="https://example.com/case-study",
    )

    verified = service.update(claim.id, verification_status=ClaimVerificationStatus.VERIFIED)

    assert service.list_verified_for_readiness() == [verified]
    assert verified.provenance == "https://example.com/case-study"


def test_updating_a_missing_claim_raises_a_not_found_error() -> None:
    service = CandidateClaimService(InMemoryClaimsRepository())

    try:
        service.update(uuid.uuid4(), text="Reworded")
    except ValueError as error:
        assert "not found" in str(error)
    else:
        raise AssertionError("Expected missing claim update to fail")
