from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class JobSnapshotView(BaseModel):
    id: uuid.UUID
    description: str
    required_skills: list[str]
    source: str
    updated_at: datetime | None = None


class MatchView(BaseModel):
    id: uuid.UUID
    overall_score: float
    semantic_score: float
    skill_score: float
    experience_score: float
    language_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    pros: list[str]
    cons: list[str]
    recommendations: list[str]
    cv_language: str
    created_at: datetime | None = None


class CvOptimizationView(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID | None
    cv_language: str
    original_tex: str
    optimized_tex: str
    improvement_summary: str
    changes: list[dict]
    created_at: datetime | None = None


class InterviewPrepView(BaseModel):
    id: uuid.UUID
    competencies_to_probe: list[str]
    technical_topics: list[str]
    negotiation_points: list[str]
    matched_stories: list[dict]
    created_at: datetime | None = None


class CoverLetterView(BaseModel):
    id: uuid.UUID
    match_id: uuid.UUID | None
    body: str
    tone: str
    created_at: datetime | None = None


class ApplicationAggregate(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    title: str
    company: str
    url: str | None
    status: str
    notes: str | None
    applied_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    job_snapshot: JobSnapshotView | None
    latest_match: MatchView | None
    latest_optimization: CvOptimizationView | None
    latest_interview_prep: InterviewPrepView | None
    latest_cover_letter: CoverLetterView | None = None
    match_count: int
    optimization_count: int
    interview_prep_count: int
    cover_letter_count: int = 0


class CoverLetterLibraryItem(BaseModel):
    """A cover letter joined with its parent application — used by GET /applications/cover-letters."""

    id: uuid.UUID
    application_id: uuid.UUID
    job_title: str
    company: str
    body: str
    tone: str
    application_status: str
    created_at: datetime | None = None
