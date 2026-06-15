from __future__ import annotations

from pydantic import BaseModel


class ScreeningAnswer(BaseModel):
    """A reusable answer to a free-text application screening question.

    Stored on the ApplyProfile so previously-answered questions can be reused
    (and matched against) when prefilling a new application form.
    """

    question: str
    answer: str
