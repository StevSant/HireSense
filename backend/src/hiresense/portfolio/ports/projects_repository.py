from __future__ import annotations

from datetime import datetime
from typing import Protocol

from hiresense.portfolio.domain import PortfolioProject


class PortfolioProjectsRepositoryPort(Protocol):
    """Snapshot store for synced portfolio projects."""

    def replace_source(self, source: str, projects: list[PortfolioProject]) -> int:
        """Atomically replace `source`'s slice of the snapshot; returns count."""
        ...

    def list_all(self) -> list[PortfolioProject]: ...

    def list_page(self, limit: int, offset: int) -> tuple[list[PortfolioProject], int]:
        """Return one page (pinned-first, then position, then source_key) and the total count."""
        ...

    def last_synced_at(self) -> datetime | None: ...
