"""Backward-compatible re-export. Import from kernel.schemas."""

from hiresense.kernel.schemas.candidate_skills_dto import CandidateSkillsDTO
from hiresense.kernel.schemas.cv_embedding_dto import CVEmbeddingDTO

__all__ = ["CandidateSkillsDTO", "CVEmbeddingDTO"]
