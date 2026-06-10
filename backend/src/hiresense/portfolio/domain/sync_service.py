from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from hiresense.portfolio.domain.sync_result import SyncResult
from hiresense.portfolio.ports import PortfolioProjectsRepositoryPort

logger = logging.getLogger(__name__)


class PortfolioSyncService:
    """Fetches every configured source and replaces its snapshot slice.

    Per-source isolation: a failing source keeps its previous slice and is
    reported in SyncResult.errors; the other sources still sync.
    """

    def __init__(self, sources: list[Any], repository: PortfolioProjectsRepositoryPort) -> None:
        self._sources = sources
        self._repository = repository

    async def sync(self) -> SyncResult:
        counts: dict[str, int] = {}
        errors: dict[str, str] = {}
        for source in self._sources:
            name = source.source_name()
            try:
                projects = await source.fetch_projects()
                counts[name] = await asyncio.to_thread(
                    self._repository.replace_source, name, projects
                )
            except Exception as exc:
                logger.exception("Portfolio sync failed for source %s", name)
                errors[name] = str(exc)
        return SyncResult(
            counts_by_source=counts, errors=errors, synced_at=datetime.now(timezone.utc)
        )
