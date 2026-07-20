from __future__ import annotations


class OptimizationError(RuntimeError):
    """Raised when CV optimization fails (LLM error, non-JSON response, bad change
    shape).

    Optimization must NOT fall back to returning the original CV byte-for-byte on
    failure — that persists a fake "success" the user reads as a tailored CV. Raising
    a dedicated error lets the API surface a 503 and keeps a genuine "no changes
    suggested" (an empty change list on a successful call) distinguishable from an
    outright failure.
    """
