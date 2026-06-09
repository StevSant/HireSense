from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class CSVImportAdapter:
    def __init__(self, import_dir: str = "./csv_imports") -> None:
        self._import_dir = Path(import_dir).resolve()

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return "csv"

    def source_type(self) -> SourceType:
        return SourceType.MANUAL

    def _resolve_inside_import_dir(self, candidate: str) -> Path:
        """Confine the requested file to the configured import directory.

        `file_path` arrives via request filters, so a relative or absolute
        path escaping the import dir (e.g. ../../etc/passwd) must be rejected.
        """
        resolved = (self._import_dir / candidate).resolve()
        if not resolved.is_relative_to(self._import_dir):
            raise ValueError(f"CSV import path escapes the import directory: {candidate}")
        return resolved

    async def fetch_jobs(
        self, filters: dict[str, Any] | None = None
    ) -> list[RawJobListing]:
        if not filters or "file_path" not in filters:
            return []
        file_path = self._resolve_inside_import_dir(str(filters["file_path"]))
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
