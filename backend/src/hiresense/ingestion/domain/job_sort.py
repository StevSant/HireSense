from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hiresense.ingestion.domain.models import NormalizedJob

# field token -> NormalizedJob attribute
_ATTR: dict[str, str] = {
    "match": "match_score",
    "posted": "posted_date",
    "title": "title",
    "company": "company",
    "location": "location",
    "source": "source",
}
_TEXT_FIELDS = {"title", "company", "location", "source"}
# Backward-compatible field aliases (the old dropdown emitted "date_*").
_ALIASES = {"date": "posted"}


def _parse(sort: str | None) -> tuple[str, bool] | None:
    """Return (field, reverse) for a valid token, else None.

    Token shape is ``<field>_<dir>`` with dir in {asc, desc}. Unknown fields
    or malformed tokens return None so callers preserve insertion order.
    """
    if not sort:
        return None
    field, _, direction = sort.rpartition("_")
    if direction not in ("asc", "desc") or not field:
        return None
    field = _ALIASES.get(field, field)
    if field not in _ATTR:
        return None
    return field, direction == "desc"


def _accessor(field: str) -> Callable[[NormalizedJob], Any]:
    attr = _ATTR[field]
    if field in _TEXT_FIELDS:
        return lambda j: (getattr(j, attr) or "").lower()
    return lambda j: getattr(j, attr)


def _is_missing(value: Any) -> bool:
    return value is None or value == ""


def sort_jobs(jobs: list[NormalizedJob], sort: str | None) -> list[NormalizedJob]:
    """Sort jobs by a ``<field>_<dir>`` token, nulls/empties always last.

    Returns a new list. An unrecognized or empty token preserves the input
    order (the API layer is responsible for substituting a default).
    """
    parsed = _parse(sort)
    if parsed is None:
        return list(jobs)
    field, reverse = parsed
    get = _accessor(field)
    present = [j for j in jobs if not _is_missing(get(j))]
    missing = [j for j in jobs if _is_missing(get(j))]
    present.sort(key=get, reverse=reverse)
    return present + missing
