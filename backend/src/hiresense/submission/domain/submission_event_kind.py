from __future__ import annotations

import enum


class SubmissionEventKind(str, enum.Enum):
    """One entry type on an attempt's append-only audit tape."""

    NAVIGATE = "navigate"
    FILL = "fill"
    CLICK = "click"
    UPLOAD = "upload"
    LLM_DECISION = "llm_decision"
    ESCALATE = "escalate"
    SUBMIT = "submit"
    ERROR = "error"
