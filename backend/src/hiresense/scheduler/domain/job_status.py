from __future__ import annotations

from enum import Enum


class JobStatus(str, Enum):
    """Outcome of one scheduled-job invocation."""

    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"
