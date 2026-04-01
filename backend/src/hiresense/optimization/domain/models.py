from __future__ import annotations

from pydantic import BaseModel, Field


class SectionChange(BaseModel):
    section_name: str
    original: str
    optimized: str
    reason: str


class OptimizationResult(BaseModel):
    id: str
    match_id: str
    job_id: str
    cv_id: str
    changes: list[SectionChange] = Field(default_factory=list)
    original_tex: str
    optimized_tex: str
    improvement_summary: str | None = None
