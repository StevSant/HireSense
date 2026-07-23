from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.claims.domain.models import CandidateClaim, ClaimVerificationStatus
from hiresense.claims.infrastructure import CandidateClaimRepository
from hiresense.infrastructure.database import Base


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    Base.metadata.drop_all(engine)


def _claim(**changes: object) -> CandidateClaim:
    values = {
        "text": "Reduced deployment time by 35%.",
        "source": "resume",
        "provenance": "Acme experience section",
    }
    values.update(changes)
    return CandidateClaim(**values)


def test_repository_persists_claim_provenance_and_verification_status(session_factory) -> None:
    repository = CandidateClaimRepository(session_factory=session_factory)

    created = repository.create(_claim(verification_status=ClaimVerificationStatus.VERIFIED))

    fetched = repository.get_by_id(created.id)
    assert fetched is not None
    assert fetched.provenance == "Acme experience section"
    assert fetched.verification_status is ClaimVerificationStatus.VERIFIED


def test_repository_exposes_only_verified_claims_to_readiness(session_factory) -> None:
    repository = CandidateClaimRepository(session_factory=session_factory)
    repository.create(_claim(text="Unverified claim"))
    verified = repository.create(
        _claim(text="Verified claim", verification_status=ClaimVerificationStatus.VERIFIED)
    )

    assert repository.list_verified() == [verified]


def test_repository_deletes_by_claim_id(session_factory) -> None:
    repository = CandidateClaimRepository(session_factory=session_factory)
    claim = repository.create(_claim())

    assert repository.delete(claim.id) is True
    assert repository.get_by_id(claim.id) is None
    assert repository.delete(uuid.uuid4()) is False
