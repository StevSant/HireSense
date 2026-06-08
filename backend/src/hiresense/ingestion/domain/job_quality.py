from __future__ import annotations

import enum


class JobQuality(str, enum.Enum):
    """Intrinsic, profile-independent quality of a job listing.

    OK           — a normal, legitimate posting (the default; shown).
    LOW_QUALITY  — thin / empty / low-value (e.g. no company and no description).
    SPAM         — MLM / franchise / commission-only / scam-style pitch.

    LOW_QUALITY and SPAM are hidden from the listing by default; a toggle
    reveals them.
    """

    OK = "ok"
    LOW_QUALITY = "low_quality"
    SPAM = "spam"
