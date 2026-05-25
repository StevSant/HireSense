from __future__ import annotations

from pydantic import BaseModel


class CreateCoverLetterTemplateRequest(BaseModel):
    name: str
    body: str
    tone: str = "professional"
    language: str = "en"
