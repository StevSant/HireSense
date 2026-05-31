from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestResult:
    """Pure domain value object capturing the outcome of an LLM connectivity test."""

    success: bool
    latency_ms: float
    response_preview: str
    error: str | None
