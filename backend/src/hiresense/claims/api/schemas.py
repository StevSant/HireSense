from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from hiresense.claims.domain.models import ClaimVerificationStatus

ClaimText = str
ClaimSource = str
ClaimProvenance = str


def _require_text(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class CreateCandidateClaimRequest(BaseModel):
    text: ClaimText = Field(max_length=10000)
    source: ClaimSource = Field(max_length=100)
    provenance: ClaimProvenance = Field(max_length=10000)

    @field_validator("text", "source", "provenance")
    @classmethod
    def require_non_empty_text(cls, value: str) -> str:
        return _require_text(value)


class UpdateCandidateClaimRequest(BaseModel):
    text: ClaimText | None = Field(default=None, max_length=10000)
    source: ClaimSource | None = Field(default=None, max_length=100)
    provenance: ClaimProvenance | None = Field(default=None, max_length=10000)
    verification_status: ClaimVerificationStatus | None = None

    @field_validator("text", "source", "provenance")
    @classmethod
    def require_non_empty_text(cls, value: str | None) -> str | None:
        return _require_text(value) if value is not None else None


class CandidateClaimResponse(BaseModel):
    id: uuid.UUID
    text: str
    source: str
    provenance: str
    verification_status: ClaimVerificationStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
