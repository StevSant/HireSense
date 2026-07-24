"""Path-safe JSONL / CSV import helpers for fallback job sources."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def resolve_inside_import_dir(import_dir: str | Path, candidate: str) -> Path:
    """Confine a relative import path to the configured import directory."""
    base = Path(import_dir).resolve()
    resolved = (base / candidate).resolve()
    if not resolved.is_relative_to(base):
        raise ValueError(f"Import path escapes the import directory: {candidate}")
    return resolved


def load_records(path: Path) -> list[dict[str, Any]]:
    """Load job records from JSON, JSONL, or CSV. Missing file → empty list."""
    if not path.exists() or not path.is_file():
        return []
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    item = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
                if isinstance(item, dict):
                    records.append(item)
        return records
    if suffix == ".json":
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict) and isinstance(data.get("jobs"), list):
            return [item for item in data["jobs"] if isinstance(item, dict)]
        if isinstance(data, dict):
            return [data]
        return []
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8") as fh:
            return [dict(row) for row in csv.DictReader(fh)]
    raise ValueError(f"Unsupported import format: {path.suffix}")


def stable_source_id(record: dict[str, Any], *, url_keys: tuple[str, ...] = ("url", "link")) -> str:
    """Prefer an explicit id; else derive from URL; else empty (caller may skip)."""
    for key in ("source_id", "id", "job_id", "guid", "slug"):
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    for key in url_keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.rstrip("/").rsplit("/", 1)[-1]
    return ""
