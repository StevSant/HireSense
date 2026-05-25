from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_iso_date(value: Any) -> datetime | None:
    """Best-effort parse of a date value emitted by a job-board API.

    Accepts:
    - ISO 8601 strings (with or without trailing Z)
    - Date-only strings (YYYY-MM-DD)
    - Unix epoch seconds as int/float
    - None / empty string

    Returns a timezone-aware UTC datetime, or None if the value can't be
    interpreted.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # ISO 8601 with trailing Z is not parseable by fromisoformat pre-3.11
        normalized = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None
