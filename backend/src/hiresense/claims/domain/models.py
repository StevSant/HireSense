from __future__ import annotations

import enum
import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel


class ClaimVerificationStatus(str, enum.Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class CandidateClaim(BaseModel):
    """A candidate statement, retained with the evidence that supports it."""

    id: uuid_mod.UUID | None = None
    text: str
    source: str
    provenance: str
    verification_status: ClaimVerificationStatus = ClaimVerificationStatus.UNVERIFIED
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
