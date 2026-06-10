from __future__ import annotations

from typing import Protocol

from hiresense.portfolio.domain import PortfolioVisit


class PortfolioEngagementPort(Protocol):
    """Read-only source of aggregated portfolio visit data."""

    async def fetch_visits(self, ref_prefix: str) -> list[PortfolioVisit]: ...
