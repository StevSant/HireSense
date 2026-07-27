from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_date(value: Any) -> date | None:
    """Parse YYYY-MM-DD (or datetime) into a date; return None on failure."""
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
