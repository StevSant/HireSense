from __future__ import annotations

from typing import Any, Protocol

from hiresense.opportunities.domain.models import RawOpportunity


class OpportunitySourcePort(Protocol):
    def source_name(self) -> str: ...

    async def fetch(self, filters: dict[str, Any] | None = None) -> list[RawOpportunity]: ...
