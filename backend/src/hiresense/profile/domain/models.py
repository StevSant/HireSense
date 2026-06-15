from __future__ import annotations

from pydantic import BaseModel, Field

from hiresense.profile.domain.apply_profile import ApplyProfile


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
    # One-per-person answer bank for application forms (Apply Assist). None until
    # the user fills it in; stored as a JSON column on the profile row.
    apply_profile: ApplyProfile | None = None
    # True when this language variant was produced by the LLM CV translator
    # rather than uploaded directly by the user.
    machine_translated: bool = False
