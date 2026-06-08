from __future__ import annotations

from typing import Protocol


class DimensionScorerPort(Protocol):
    """Snapshots a job's per-dimension matching scores at outcome time.

    Implemented by a bootstrap adapter that runs the configured matching
    dimension scorers for the job (by id) against the current profile and
    returns ``{dimension_name: score}``. Returns ``None`` when the job,
    profile, scorers, or LLM are unavailable, or on any failure — in which
    case the signal is still recorded but carries no dimension scores and so
    contributes nothing to weight nudging.
    """

    async def score_dimensions(self, job_id: str) -> dict[str, float] | None: ...
