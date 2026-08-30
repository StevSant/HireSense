from __future__ import annotations

from pydantic import BaseModel, Field

from hiresense.submission.domain.answer_source import AnswerSource


class FieldAnswer(BaseModel):
    """A value the agent intends to type into one form field."""

    selector: str
    canonical_key: str | None = None
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: AnswerSource
    rationale: str | None = None
