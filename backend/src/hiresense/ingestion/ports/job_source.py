from __future__ import annotations

from typing import Any, Protocol

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class JobSourcePort(Protocol):
    def source_name(self) -> str: ...
    def source_type(self) -> SourceType: ...
    def supports_snapshot_closure(self) -> bool:
        """True if one fetch returns the source's COMPLETE current open set,
        so a previously-seen job missing from results implies it closed."""
        ...

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]: ...
