from __future__ import annotations

from pydantic import BaseModel


class OptimizationRequestDTO(BaseModel):
    match_id: str
    job_id: str
    cv_id: str


class TexDiffDTO(BaseModel):
    optimization_id: str
    original_path: str
    diff: str
    modified_tex: str
