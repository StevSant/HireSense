from __future__ import annotations

from typing import Protocol

from hiresense.submission.domain.field_answer import FieldAnswer
from hiresense.submission.domain.form_field import FormField


class FormAnswerPort(Protocol):
    """Answers the form fields the deterministic profile map could not.

    The seam between the pure agent and whatever generates answers. Kept
    narrow on purpose: the agent hands over only the residual required fields
    plus the material an answer may be grounded in, and gets back scored
    candidates that the grounding validator still has to clear.
    """

    async def answer(
        self,
        *,
        fields: list[FormField],
        job_text: str,
        prefill: dict[str, object],
        claim_texts: list[str],
        screening_answers: list[tuple[str, str]],
    ) -> list[FieldAnswer]: ...
