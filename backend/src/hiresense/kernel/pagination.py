from __future__ import annotations


def resolve_page_limit(requested: int | None, *, default: int, maximum: int) -> int:
    """Resolve the effective page size for a list endpoint.

    Falls back to ``default`` when the client omits ``?limit`` (so existing
    single-page consumers keep their behaviour), and clamps any explicit request
    to ``maximum`` so a single call can never pull an unbounded page. Callers
    pass ``offset`` straight through (validated ``>= 0`` at the query layer).
    """
    if requested is None:
        return default
    return min(requested, maximum)
