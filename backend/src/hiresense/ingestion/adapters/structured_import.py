"""Shared base for JSONL/CSV import fallback job sources."""

from __future__ import annotations

from typing import Any

from hiresense.ingestion.adapters._jsonl_import import (
    load_records,
    resolve_inside_import_dir,
    stable_source_id,
)
from hiresense.ingestion.domain.models import RawJobListing
from hiresense.kernel.value_objects import SourceType


class StructuredImportAdapter:
    """Manual import adapter parameterized by source name and default filename."""

    source: str = "import"
    default_filename: str = "jobs.jsonl"

    def __init__(self, *, import_dir: str, default_filename: str | None = None) -> None:
        self._import_dir = import_dir
        if default_filename:
            self.default_filename = default_filename
        self.last_pages_fetched = 0
        self.last_rejected_malformed = 0
        self.last_parse_failures = 0

    def supports_snapshot_closure(self) -> bool:
        return False

    def source_name(self) -> str:
        return self.source

    def source_type(self) -> SourceType:
        return SourceType.MANUAL

    async def fetch_jobs(self, filters: dict[str, Any] | None = None) -> list[RawJobListing]:
        self.last_pages_fetched = 0
        self.last_rejected_malformed = 0
        self.last_parse_failures = 0
        filename = (filters or {}).get("file_path") or self.default_filename
        path = resolve_inside_import_dir(self._import_dir, str(filename))
        try:
            records, parse_failures = load_records(path)
        except ValueError:
            self.last_parse_failures += 1
            raise
        self.last_parse_failures += parse_failures
        self.last_pages_fetched = 1 if path.exists() else 0
        jobs: list[RawJobListing] = []
        seen: set[str] = set()
        for record in records:
            source_id = stable_source_id(record)
            if not source_id:
                self.last_rejected_malformed += 1
                continue
            if source_id in seen:
                continue
            if not (record.get("title") and (record.get("company") or record.get("company_name"))):
                self.last_rejected_malformed += 1
                continue
            seen.add(source_id)
            jobs.append(RawJobListing(source=self.source, source_id=source_id, raw_data=record))
        return jobs


class IndeedAdapter(StructuredImportAdapter):
    source = "indeed"
    default_filename = "indeed_jobs.jsonl"


class WellfoundAdapter(StructuredImportAdapter):
    source = "wellfound"
    default_filename = "wellfound_jobs.jsonl"


class GlassdoorAdapter(StructuredImportAdapter):
    source = "glassdoor"
    default_filename = "glassdoor_jobs.jsonl"


class MonsterAdapter(StructuredImportAdapter):
    source = "monster"
    default_filename = "monster_jobs.jsonl"
