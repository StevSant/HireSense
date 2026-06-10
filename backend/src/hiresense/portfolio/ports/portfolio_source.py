from __future__ import annotations

from typing import Protocol

from hiresense.portfolio.domain import PortfolioProject


class PortfolioSourcePort(Protocol):
    """A read-only external source of portfolio projects."""

    def source_name(self) -> str: ...

    async def fetch_projects(self) -> list[PortfolioProject]: ...
