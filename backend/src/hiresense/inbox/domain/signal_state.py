from __future__ import annotations

from enum import Enum


class SignalState(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DISMISSED = "dismissed"
