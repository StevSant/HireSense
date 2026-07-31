from __future__ import annotations

from enum import Enum


class UpsertResult(str, Enum):
    INSERTED = "inserted"
    UPDATED = "updated"
    REOPENED = "reopened"
    UNCHANGED = "unchanged"
