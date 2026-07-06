from __future__ import annotations

from pydantic import BaseModel


class Firmographics(BaseModel):
    """Basic company facts, from an external provider or the LLM. All optional."""

    industry: str | None = None
    company_size: str | None = None
    headquarters: str | None = None
    website: str | None = None
