from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from hiresense.portfolio.domain.portfolio_visit import PortfolioVisit

if TYPE_CHECKING:
    from hiresense.portfolio.ports.engagement_source import PortfolioEngagementPort

logger = logging.getLogger(__name__)


class PortfolioEngagementService:
    """Fetches portfolio visits, derives application_id from ref prefix, sorts desc."""

    def __init__(self, source: PortfolioEngagementPort | Any, *, ref_prefix: str) -> None:
        self._source = source
        self._prefix = ref_prefix

    async def visits(self) -> list[PortfolioVisit]:
        try:
            raw = await self._source.fetch_visits(self._prefix)
        except Exception:
            logger.warning("PortfolioEngagementService: failed to fetch visits", exc_info=True)
            return []

        result: list[PortfolioVisit] = []
        tag = f"{self._prefix}-"
        for visit in raw:
            application_id = visit.ref.removeprefix(tag) if visit.ref.startswith(tag) else None
            result.append(visit.model_copy(update={"application_id": application_id}))

        result.sort(key=lambda v: v.last_seen, reverse=True)
        return result
