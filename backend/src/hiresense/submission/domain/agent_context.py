from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentContext:
    """Everything the form agent may ground an answer in, for one attempt.

    Deliberately a closed set: if a value is not reachable from here, the agent
    has no business asserting it on the candidate's behalf.
    """

    prefill: dict[str, Any] = field(default_factory=dict)
    claim_texts: list[str] = field(default_factory=list)
    screening_answers: list[tuple[str, str]] = field(default_factory=list)
    job_text: str = ""
    needs_cv_upload: bool = False
    needs_letter_upload: bool = False
