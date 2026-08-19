from __future__ import annotations

from enum import Enum


class JobHistoryEventType(str, Enum):
    """What was observed to happen to a job in one run.

    Mirrors UpsertResult minus UNCHANGED (a no-op is not history), plus
    CLOSED, which no upsert path can produce.
    """

    INSERTED = "inserted"
    UPDATED = "updated"
    REOPENED = "reopened"
    CLOSED = "closed"
