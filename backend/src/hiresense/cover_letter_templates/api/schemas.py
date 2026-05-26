from __future__ import annotations

from pydantic import BaseModel


class CreateCoverLetterTemplateRequest(BaseModel):
    name: str
    tone: str = "professional"
    language: str = "en"
    opening: str = ""
    body: str = ""
    signature: str = ""


class UpdateCoverLetterTemplateRequest(BaseModel):
    name: str | None = None
    tone: str | None = None
    language: str | None = None
    opening: str | None = None
    body: str | None = None
    signature: str | None = None
