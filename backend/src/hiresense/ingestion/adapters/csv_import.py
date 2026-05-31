from __future__ import annotations

import csv
import uuid
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class CSVImportAdapter:
    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "csv"

    def source_type(self) -> SourceType:
        return SourceType.MANUAL

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        if not filters or "file_path" not in filters:
            return []
        file_path = filters["file_path"]
        jobs: list[RawJobListing] = []
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                jobs.append(
                    RawJobListing(
                        source="csv",
                        source_id=str(uuid.uuid4()),
                        raw_data=dict(row),
                    )
                )
        return jobs
