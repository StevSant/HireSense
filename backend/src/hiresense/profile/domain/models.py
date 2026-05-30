from __future__ import annotations

from pydantic import BaseModel, Field


class CVSection(BaseModel):
    name: str
    content: str


class CandidateProfile(BaseModel):
    id: str
    name: str
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    sections: list[CVSection] = Field(default_factory=list)
    raw_tex: str = ""
    language: str = "en"
    skills: list[str] = Field(default_factory=list)
    embedding: list[float] | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
