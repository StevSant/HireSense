from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.claims.api.dependencies import get_candidate_claim_service
from hiresense.claims.api.routes import router
from hiresense.claims.domain.models import CandidateClaim, ClaimVerificationStatus
from hiresense.identity.api.dependencies import require_auth


class FakeCandidateClaimService:
    def __init__(self) -> None:
        self.claims: dict[uuid.UUID, CandidateClaim] = {}

    def create(self, *, text: str, source: str, provenance: str) -> CandidateClaim:
        claim = CandidateClaim(
            id=uuid.uuid4(),
            text=text,
            source=source,
            provenance=provenance,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.claims[claim.id] = claim
        return claim

    def get(self, claim_id: uuid.UUID) -> CandidateClaim:
        claim = self.claims.get(claim_id)
        if claim is None:
            raise ValueError(f"Candidate claim {claim_id} not found")
        return claim

    def list(self, status: ClaimVerificationStatus | None = None) -> list[CandidateClaim]:
        claims = list(self.claims.values())
        return (
            [claim for claim in claims if claim.verification_status == status] if status else claims
        )

    def update(self, claim_id: uuid.UUID, **fields: object) -> CandidateClaim:
        claim = self.get(claim_id).model_copy(update=fields)
        self.claims[claim_id] = claim
        return claim

    def remove(self, claim_id: uuid.UUID) -> None:
        self.get(claim_id)
        del self.claims[claim_id]


def _client(service: FakeCandidateClaimService) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_candidate_claim_service] = lambda: service
    app.dependency_overrides[require_auth] = lambda: "candidate"
    app.include_router(router)
    return TestClient(app)


def test_authenticated_client_can_create_and_verify_a_claim() -> None:
    service = FakeCandidateClaimService()
    client = _client(service)

    created = client.post(
        "/claims",
        json={
            "text": "Reduced batch processing time by 40%.",
            "source": "portfolio",
            "provenance": "https://example.com/case-study",
        },
    )

    assert created.status_code == 201
    claim_id = created.json()["id"]
    updated = client.patch(f"/claims/{claim_id}", json={"verification_status": "verified"})
    assert updated.status_code == 200
    assert updated.json()["verification_status"] == "verified"


def test_claims_routes_require_authentication() -> None:
    app = FastAPI()
    app.include_router(router)

    response = TestClient(app).get("/claims")

    assert response.status_code == 401


def test_claim_creation_rejects_blank_provenance() -> None:
    client = _client(FakeCandidateClaimService())

    response = client.post(
        "/claims",
        json={"text": "Real claim", "source": "resume", "provenance": "   "},
    )

    assert response.status_code == 422
