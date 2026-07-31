"""Sort token helpers for opportunities list endpoints."""

from __future__ import annotations

_FIELD_ALIASES = {
    "match": "match",
    "relevance": "match",
    "title": "title",
    "country": "country",
    "language": "language",
    "cost": "cost",
    "when": "when",
    "date": "when",
    "start": "when",
    "source": "source",
    "deadline": "deadline",
}

# Sorts that need scored/derived values and therefore run in memory.
_MEMORY_FIELDS = frozenset({"match", "language", "cost"})


def parse_sort_token(sort: str | None) -> tuple[str, str]:
    """Return ``(field, direction)`` with ``direction`` in ``asc|desc``."""
    raw = (sort or "match_desc").strip().lower()
    if raw in {"relevance_desc", "match_desc"}:
        return "match", "desc"
    if raw in {"relevance_asc", "match_asc"}:
        return "match", "asc"
    if raw == "date_asc":
        return "when", "asc"
    if raw == "date_desc":
        return "when", "desc"
    if "_" not in raw:
        field = _FIELD_ALIASES.get(raw, "when")
        return field, "desc" if field == "match" else "asc"
    field_raw, _, direction = raw.rpartition("_")
    if direction not in {"asc", "desc"}:
        return "when", "asc"
    field = _FIELD_ALIASES.get(field_raw, field_raw)
    return field, direction


def requires_memory_sort(sort: str | None) -> bool:
    field, _ = parse_sort_token(sort)
    return field in _MEMORY_FIELDS
