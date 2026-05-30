from __future__ import annotations

import enum
import uuid as uuid_mod
from datetime import datetime

from pydantic import BaseModel, Field


class JobSnapshotSource(str, enum.Enum):
    INGESTED = "ingested"
    MANUAL = "manual"
    LLM_EXTRACTED = "llm_extracted"


class ApplicationJobSnapshot(BaseModel):
    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    description: str = ""
    required_skills: list[str] = Field(default_factory=list)
    source: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplicationMatch(BaseModel):
    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    overall_score: float
    semantic_score: float
    skill_score: float
    experience_score: float
    language_score: float
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    cv_language: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplicationCvOptimization(BaseModel):
    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    match_id: uuid_mod.UUID | None = None
    cv_language: str
    original_tex: str
    optimized_tex: str
    improvement_summary: str = ""
    changes: list[dict] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplicationCoverLetter(BaseModel):
    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    match_id: uuid_mod.UUID | None = None
    body: str
    tone: str = "professional"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApplicationInterviewPrep(BaseModel):
    id: uuid_mod.UUID | None = None
    application_id: uuid_mod.UUID
    competencies_to_probe: list[str] = Field(default_factory=list)
    technical_topics: list[str] = Field(default_factory=list)
    negotiation_points: list[str] = Field(default_factory=list)
    matched_stories: list[dict] = Field(default_factory=list)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
