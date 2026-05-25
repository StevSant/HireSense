from __future__ import annotations

from pydantic import BaseModel


class UpdateCoverLetterTemplateRequest(BaseModel):
    name: str | None = None
    body: str | None = None
    tone: str | None = None
    language: str | None = None
