from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.admin.infrastructure import LLMUsageLog, UsageBucket, UsageTotals


class LLMUsageLogRepositoryPort(Protocol):
    """Persistence and aggregation for LLM usage records."""

    def insert(
        self,
        *,
        feature_key: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        latency_ms: float,
        success: bool,
        error: str | None,
        user_id: str | None,
    ) -> None: ...

    def totals(self, since: datetime | None = None) -> UsageTotals: ...

    def timeseries_daily(self, since: datetime) -> list[UsageBucket]: ...

    def breakdown(self, dimension: str, since: datetime | None = None) -> list[UsageBucket]: ...

    def list_recent(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        provider: str | None = None,
        model: str | None = None,
        feature_key: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[LLMUsageLog]: ...
