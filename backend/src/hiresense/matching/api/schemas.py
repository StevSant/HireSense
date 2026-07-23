from __future__ import annotations

import uuid as uuid_mod

from pydantic import BaseModel

from hiresense.matching.domain.eligibility import EligibilityStatus


class EvaluateRequest(BaseModel):
    job_id: str | None = None
    profile_id: str | None = None
    job_title: str | None = None
    company: str | None = None
    description: str | None = None
    skills: list[str] = []
    location: str | None = None
    requires_existing_work_authorization: bool | None = None
    visa_sponsorship_available: bool | None = None


class DimensionResultResponse(BaseModel):
    dimension: str
    score: float
    rationale: str
    weight: int


class EligibilityResponse(BaseModel):
    status: EligibilityStatus
    rationale: str


class EvaluationResponse(BaseModel):
    composite_score: float
    job_title: str
    company: str
    dimensions: list[DimensionResultResponse]
    eligibility: EligibilityResponse


class BatchEvaluateRequest(BaseModel):
    tracked_app_ids: list[uuid_mod.UUID] = []
    include_ingested: bool = False
    profile_id: str | None = None


class BatchResultResponse(BaseModel):
    job_title: str
    company: str
    source: str
    source_id: str
    composite_score: float
    dimensions: list[DimensionResultResponse]
    eligibility: EligibilityResponse
    failed: bool = False


class BatchEvaluationResponse(BaseModel):
    total_jobs: int
    results: list[BatchResultResponse]
