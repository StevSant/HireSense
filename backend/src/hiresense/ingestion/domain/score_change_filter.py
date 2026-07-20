from __future__ import annotations

from collections.abc import Iterable

from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.ports.jobs_repository import ScoreUpdate

# Scores within this absolute delta count as unchanged. Recomputation is
# deterministic, so this only guards against float representation noise.
_SCORE_EPSILON = 1e-9


def changed_score_updates(
    jobs: Iterable[NormalizedJob],
    originals: dict[str, tuple[float | None, float | None]],
) -> list[ScoreUpdate]:
    """ScoreUpdate rows only for jobs whose scores differ from the loaded value.

    The list read path recomputes match/semantic scores on every request. Without
    this diff it re-persists the WHOLE corpus on each GET — a full-table UPDATE
    even on plain pagination or a sort-only reload. Emitting only genuinely
    changed rows makes write volume proportional to real score changes rather
    than corpus size (#132).

    ``originals`` maps job id → the ``(match_score, semantic_score)`` pair read
    from the store before the request-scoped rescoring ran.
    """
    updates: list[ScoreUpdate] = []
    for job in jobs:
        prev = originals.get(job.id)
        if prev is None:
            # Id not present at load time (shouldn't happen on the read path) —
            # persist it rather than silently drop a real change.
            updates.append(ScoreUpdate(job.id, job.match_score, job.semantic_score))
            continue
        prev_match, prev_semantic = prev
        if _score_differs(prev_match, job.match_score) or _score_differs(
            prev_semantic, job.semantic_score
        ):
            updates.append(ScoreUpdate(job.id, job.match_score, job.semantic_score))
    return updates


def _score_differs(previous: float | None, current: float | None) -> bool:
    """True when a score changed, treating None↔value transitions as changes and
    None↔None / near-equal floats as unchanged."""
    if previous is None or current is None:
        return previous is not current
    return abs(previous - current) > _SCORE_EPSILON
