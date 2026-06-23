from __future__ import annotations

from enum import Enum


class DraftStatus(str, Enum):
    """Outcome of drafting one job."""

    DRAFTED = "drafted"   # application + all artifacts generated
    PARTIAL = "partial"   # application created, some artifact generation failed
    FAILED = "failed"     # could not even create the application
