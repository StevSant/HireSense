"""In-process per-source ingestion health tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel


class SourceHealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"


class SourceHealth(BaseModel):
    source: str
    status: SourceHealthStatus = SourceHealthStatus.DISABLED
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    duration_ms: float | None = None
    pages_fetched: int = 0
    jobs_discovered: int = 0
    jobs_created: int = 0
    jobs_updated: int = 0
    jobs_deduplicated: int = 0
    jobs_rejected_malformed: int = 0
    rate_limited_count: int = 0
    parse_failures: int = 0
    last_error: str | None = None


class SourceRunStats(BaseModel):
    """Counters recorded for a single source fetch within one orchestrator run."""

    pages_fetched: int = 0
    jobs_discovered: int = 0
    jobs_created: int = 0
    jobs_updated: int = 0
    jobs_deduplicated: int = 0
    jobs_rejected_malformed: int = 0
    rate_limited_count: int = 0
    parse_failures: int = 0
    error: str | None = None
    success: bool = True


class SourceHealthTracker:
    """Process-local health map (same single-worker assumption as metrics)."""

    def __init__(self) -> None:
        self._by_source: dict[str, SourceHealth] = {}

    def snapshot(self) -> list[SourceHealth]:
        return [h.model_copy() for h in self._by_source.values()]

    def get(self, source: str) -> SourceHealth:
        return self._by_source.setdefault(source, SourceHealth(source=source)).model_copy()

    def mark_disabled(self, source: str, *, reason: str | None = None) -> None:
        health = self._by_source.setdefault(source, SourceHealth(source=source))
        health.status = SourceHealthStatus.DISABLED
        if reason:
            health.last_error = reason

    def mark_not_configured(self, source: str, *, reason: str | None = None) -> None:
        health = self._by_source.setdefault(source, SourceHealth(source=source))
        health.status = SourceHealthStatus.NOT_CONFIGURED
        if reason:
            health.last_error = reason

    def record_run(self, source: str, *, duration_ms: float, stats: SourceRunStats) -> None:
        now = datetime.now(timezone.utc)
        health = self._by_source.setdefault(source, SourceHealth(source=source))
        health.last_attempt_at = now
        health.duration_ms = duration_ms
        health.pages_fetched = stats.pages_fetched
        health.jobs_discovered = stats.jobs_discovered
        health.jobs_created = stats.jobs_created
        health.jobs_updated = stats.jobs_updated
        health.jobs_deduplicated = stats.jobs_deduplicated
        health.jobs_rejected_malformed = stats.jobs_rejected_malformed
        health.rate_limited_count = stats.rate_limited_count
        health.parse_failures = stats.parse_failures
        if stats.success and not stats.error:
            health.last_success_at = now
            health.last_error = None
            if stats.parse_failures or stats.rate_limited_count or stats.jobs_rejected_malformed:
                health.status = SourceHealthStatus.DEGRADED
            else:
                health.status = SourceHealthStatus.HEALTHY
        else:
            health.last_error = stats.error or "fetch failed"
            health.status = SourceHealthStatus.FAILING

    def as_dict(self) -> list[dict[str, Any]]:
        return [h.model_dump(mode="json") for h in self.snapshot()]
