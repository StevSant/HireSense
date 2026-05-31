from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpenJob:
    id: str
    identity_key: str
    missed_count: int


def detect_closures(
    *, seen: set[str], open_jobs: list[OpenJob], threshold: int
) -> tuple[dict[str, int], list[str]]:
    """Pure disappearance rule. Returns (new missed_count per job, ids to close).

    Caller must ONLY invoke this for snapshot-capable sources after a SUCCESSFUL
    fetch (empty allowed). A job seen this run resets to 0; a missing job
    increments and closes once it reaches `threshold`.
    """
    updated: dict[str, int] = {}
    to_close: list[str] = []
    for job in open_jobs:
        if job.identity_key in seen:
            updated[job.id] = 0
            continue
        nxt = job.missed_count + 1
        updated[job.id] = nxt
        if nxt >= threshold:
            to_close.append(job.id)
    return updated, to_close
