from __future__ import annotations

from datetime import datetime, timezone


def as_utc(value: datetime | None) -> datetime | None:
    """Return ``value`` as timezone-aware UTC, or None.

    Naive datetimes are *assumed* to be UTC rather than rejected: they reach us
    from query params (FastAPI parses ``?date_from=2026-08-01`` to a naive
    datetime) and from sources whose feeds omit an offset, while stored
    ``posted_date`` values are aware. Comparing the two raises TypeError, which
    surfaced as a 500 on the job list's Date From filter.
    """
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
