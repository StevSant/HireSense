from __future__ import annotations

import enum


class AnswerSource(str, enum.Enum):
    """Where a filled field's value came from.

    The distinction is load-bearing: DETERMINISTIC_MAP and PROFILE answers are
    the candidate's own data copied verbatim and are exempt from grounding
    checks, while LLM answers are generated and must be validated against the
    candidate's data before they are trusted.
    """

    DETERMINISTIC_MAP = "deterministic_map"
    PROFILE = "profile"
    CLAIMS = "claims"
    JOB_CONTEXT = "job_context"
    LLM = "llm"
