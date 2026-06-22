from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable


@dataclass(frozen=True)
class JobDefinition:
    """Wiring record for one scheduled job: how to run it, when, and how to
    count what it affected. Exactly one of ``cron``/``interval_hours`` is set.

    ``cron`` is also used as the human-facing cadence label in the status API;
    for interval jobs a synthetic label is supplied (e.g. ``"every 24h"``).
    """

    name: str
    run: Callable[[], Awaitable[Any]]
    cron: str | None
    interval_hours: int | None
    count_items: Callable[[Any], int | None]
    default_enabled: bool = True

    @property
    def cadence_label(self) -> str:
        return self.cron if self.cron is not None else f"every {self.interval_hours}h"
