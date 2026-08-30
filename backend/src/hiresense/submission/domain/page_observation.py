from __future__ import annotations

from pydantic import BaseModel, Field

from hiresense.submission.domain.form_field import FormField


class PageObservation(BaseModel):
    """A sanitized snapshot of the application page the runner is looking at.

    This is untrusted external content. page_text is stripped of scripts and
    styles by the runner's serializer before it ever reaches a prompt.
    """

    url: str
    title: str = ""
    fields: list[FormField] = Field(default_factory=list)
    captcha_detected: bool = False
    page_text: str = ""

    @property
    def required_fields(self) -> list[FormField]:
        return [f for f in self.fields if f.required]
