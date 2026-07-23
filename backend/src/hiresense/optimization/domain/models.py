from __future__ import annotations

import uuid
from typing import Literal, TypeAlias

from pydantic import BaseModel, Field


class SectionChange(BaseModel):
    section_name: str
    original: str
    optimized: str
    reason: str


ClaimBlockerReason: TypeAlias = Literal[
    "missing_exact_anchor",
    "unsupported_job_skill",
    "unsupported_numeric_claim",
]


class BlockedClaim(BaseModel):
    change: SectionChange
    reason: ClaimBlockerReason


class VerifiedClaimEvidence(BaseModel):
    """Human-verified ledger evidence used to support a generated CV edit."""

    claim_id: uuid.UUID | None = None
    text: str
    source: str
    provenance: str


class SupportedChangeEvidence(BaseModel):
    change: SectionChange
    claims: list[VerifiedClaimEvidence] = Field(default_factory=list)


class ClaimReadiness(BaseModel):
    ready: bool
    supported_changes: list[SectionChange] = Field(default_factory=list)
    blocked_changes: list[BlockedClaim] = Field(default_factory=list)
    supported_evidence: list[SupportedChangeEvidence] = Field(default_factory=list)


class OptimizationResult(BaseModel):
    id: str
    match_id: str
    job_id: str
    cv_id: str
    changes: list[SectionChange] = Field(default_factory=list)
    original_tex: str
    optimized_tex: str
    improvement_summary: str | None = None
    claim_readiness: ClaimReadiness = Field(default_factory=lambda: ClaimReadiness(ready=True))
