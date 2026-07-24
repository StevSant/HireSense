"""CrunchBoard title parsing helpers (pure domain — no feedparser)."""

from __future__ import annotations

import re

_TITLE_RE = re.compile(
    r"^(?P<title>.+?)\s+at\s+(?P<company>.+?)(?:\s+\((?P<location>.+)\))?$",
    re.IGNORECASE,
)


def parse_crunchboard_title(title: str) -> tuple[str, str, str]:
    """Split 'Role at Company (Location)' into title, company, location."""
    match = _TITLE_RE.match(title.strip())
    if not match:
        return title.strip(), "", ""
    return (
        match.group("title").strip(),
        match.group("company").strip(),
        (match.group("location") or "").strip(),
    )
