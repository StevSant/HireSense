from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from hiresense.admin.ports import LLMUsageLogRepositoryPort

if TYPE_CHECKING:
    from hiresense.admin.infrastructure import UsageBucket, UsageTotals


@dataclass(frozen=True)
class DashboardSummary:
    today: UsageTotals
    this_month: UsageTotals
    all_time: UsageTotals


class UsageAggregator:
    """Read-side service for the admin usage dashboard."""

    def __init__(self, repo: LLMUsageLogRepositoryPort) -> None:
        self._repo = repo

    def summary(self) -> DashboardSummary:
        now = datetime.now(timezone.utc)
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_month = start_of_today.replace(day=1)
        return DashboardSummary(
            today=self._repo.totals(since=start_of_today),
            this_month=self._repo.totals(since=start_of_month),
            all_time=self._repo.totals(),
        )

    def timeseries(self, days: int = 30) -> list[UsageBucket]:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        return self._repo.timeseries_daily(since=since)

    def breakdown(self, dimension: str, days: int | None = 30) -> list[UsageBucket]:
        since = None if days is None else datetime.now(timezone.utc) - timedelta(days=days)
        return self._repo.breakdown(dimension=dimension, since=since)

    def recent_calls(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        provider: str | None = None,
        model: str | None = None,
        feature_key: str | None = None,
        days: int | None = None,
    ):
        since = None if days is None else datetime.now(timezone.utc) - timedelta(days=days)
        return self._repo.list_recent(
            limit=limit,
            offset=offset,
            provider=provider,
            model=model,
            feature_key=feature_key,
            since=since,
        )

    def export_csv(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        feature_key: str | None = None,
        days: int | None = 90,
    ) -> str:
        rows = self.recent_calls(
            limit=10000, offset=0, provider=provider, model=model,
            feature_key=feature_key, days=days,
        )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "created_at", "feature_key", "provider", "model",
            "input_tokens", "output_tokens", "total_tokens",
            "cost_usd", "latency_ms", "success", "error",
        ])
        for r in rows:
            writer.writerow([
                r.created_at.isoformat() if r.created_at else "",
                r.feature_key, r.provider, r.model,
                r.input_tokens, r.output_tokens, r.total_tokens,
                f"{r.cost_usd:.6f}", f"{r.latency_ms:.2f}",
                r.success, r.error or "",
            ])
        return buf.getvalue()
