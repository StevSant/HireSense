from __future__ import annotations

from enum import Enum


class EmailSignalKind(str, Enum):
    """The status-changing signal an email carries (or OTHER)."""

    REJECTION = "rejection"
    INTERVIEW = "interview"
    OFFER = "offer"
    OTHER = "other"
