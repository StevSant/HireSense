"""Infer attendance cost when sources don't publish an explicit fee field."""

from __future__ import annotations

import re
from typing import Literal

CostLabel = Literal["Funded", "Free", "Paid", "Likely paid", "Unknown"]

_FREE_RE = re.compile(
    r"\b("
    r"free(\s+to\s+attend)?|"
    r"no[- ]?fee|"
    r"gratis|"
    r"complimentary|"
    r"cost[- ]?free|"
    r"free[- ]?(admission|entry|event|conference|summit|meetup)"
    r")\b",
    re.IGNORECASE,
)
_PAID_URL_RE = re.compile(
    r"("
    r"eventbrite\.|"
    r"ti\.to/|"
    r"ticketailor\.|"
    r"ticket(?:s)?(?:[-_/]|$)|"
    r"pricing|"
    r"buy[-_]?ticket|"
    r"registration[-_]?fee|"
    r"hopin\.com|"
    r"sessionize\.com/[^/]+/tickets"
    r")",
    re.IGNORECASE,
)
_PAID_TEXT_RE = re.compile(
    r"\b("
    r"paid(\s+event)?|"
    r"ticket(s|ing)?|"
    r"early[- ]bird|"
    r"registration\s+fee|"
    r"conference\s+fee|"
    r"from\s+\$\d|"
    r"usd\s*\d|"
    r"€\d|£\d|\$\d"
    r")\b",
    re.IGNORECASE,
)

# Industry conferences almost always charge; use this when the source is silent.
_TYPICALLY_PAID_KINDS = frozenset({"conference", "cfp", "event", "summer_school"})


def infer_attendance_cost(
    *,
    title: str = "",
    description: str = "",
    url: str = "",
    apply_url: str | None = None,
    funding: str | None = None,
    kind: str | None = None,
) -> CostLabel:
    """Best-effort attendance cost label.

    confs.tech does not publish fee fields. When there is no free/funded signal,
    conference-like kinds default to ``Likely paid`` (typical for industry events)
    instead of ``Unknown``.
    """
    if kind in {"grant", "fellowship"}:
        return "Funded"
    funding_l = (funding or "").strip().lower()
    if funding_l and funding_l not in {"none", "n/a", "na", "no", "-", "unfunded", "self-funded"}:
        return "Funded"

    blob = " ".join(p for p in [title, description, funding or ""] if p)
    urls = " ".join(p for p in [url, apply_url or ""] if p)

    if _FREE_RE.search(blob) or _FREE_RE.search(urls):
        return "Free"
    if _PAID_URL_RE.search(urls) or _PAID_TEXT_RE.search(blob):
        return "Paid"
    if (kind or "") in _TYPICALLY_PAID_KINDS:
        return "Likely paid"
    return "Unknown"
