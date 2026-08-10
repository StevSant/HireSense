from __future__ import annotations

from pydantic import BaseModel


class CandidateSkillsDTO(BaseModel):
    skills: list[str]
    experience_summary: str
    language: str
