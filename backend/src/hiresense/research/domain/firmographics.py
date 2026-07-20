from __future__ import annotations

from pydantic import BaseModel


class Firmographics(BaseModel):
    """Basic company facts, from an external provider or the LLM. All optional."""

    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    website: str | None = None
    # Plain-text "about" blurb from a source-captured company profile (e.g. a job
    # board's company page). Grounds the research prompt and is surfaced as an
    # About block; may be non-English. None when no source profile was captured.
    description: str | None = None
