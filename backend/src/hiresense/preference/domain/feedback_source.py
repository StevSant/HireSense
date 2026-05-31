from __future__ import annotations

import enum


class FeedbackSource(str, enum.Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"
