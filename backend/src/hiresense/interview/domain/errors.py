from __future__ import annotations


class InterviewPrepError(RuntimeError):
    """Raised when interview prep generation fails (LLM error, unparseable
    response, malformed matched_stories).

    The service must NOT swallow the failure and return a benign placeholder — that
    gets persisted as real prep, hiding genuine bugs and outages. Raising a
    dedicated error lets the API surface a 503 and keeps the placeholder out of the
    database.
    """
