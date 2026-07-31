from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from hiresense.ingestion.adapters._jsonl_import import load_records, resolve_inside_import_dir
from hiresense.opportunities.domain.models import RawOpportunity

logger = logging.getLogger(__name__)


class CuratedImportAdapter:
    """Load operator-maintained opportunity records from YAML/JSONL/JSON/CSV."""

    def __init__(
        self,
        *,
        import_dir: str,
        filename: str = "opportunities.yml",
    ) -> None:
        self._import_dir = import_dir
        self._filename = filename

    def source_name(self) -> str:
        return "curated"

    async def fetch(self, filters: dict[str, Any] | None = None) -> list[RawOpportunity]:
        filename = (filters or {}).get("filename") or self._filename
        try:
            path = resolve_inside_import_dir(self._import_dir, str(filename))
        except ValueError as exc:
            logger.warning("Curated opportunities path rejected: %s", exc)
            return []
        records = self._load(path)
        results: list[RawOpportunity] = []
        for idx, record in enumerate(records):
            source_id = self._stable_id(record, idx)
            if not source_id:
                continue
            results.append(RawOpportunity(source="curated", source_id=source_id, raw_data=record))
        return results

    def _load(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists() or not path.is_file():
            return []
        suffix = path.suffix.lower()
        if suffix in {".yml", ".yaml"}:
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
            if isinstance(data, dict):
                items = data.get("opportunities") or data.get("items") or []
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
            return []
        records, _failures = load_records(path)
        return records

    @staticmethod
    def _stable_id(record: dict[str, Any], idx: int) -> str:
        for key in ("source_id", "id", "slug"):
            value = record.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        url = (record.get("url") or record.get("apply_url") or "").strip()
        if url:
            return url.rstrip("/").rsplit("/", 1)[-1] or f"curated-{idx}"
        title = (record.get("title") or record.get("name") or "").strip()
        return title.lower().replace(" ", "-")[:64] if title else ""
