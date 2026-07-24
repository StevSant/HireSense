"""Shared field mapping helpers for import-based job normalizers."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html


def first_str(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return default


def first_bool(data: dict[str, Any], *keys: str) -> bool | None:
    for key in keys:
        if key not in data or data[key] is None:
            continue
        value = data[key]
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "y"}:
            return True
        if text in {"0", "false", "no", "n"}:
            return False
    return None


def as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(";", ",").split(",")]
        return [p for p in parts if p]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("skill") or item.get("label")
                if isinstance(name, str) and name.strip():
                    out.append(name.strip())
        return out
    return []


def parse_posted_date(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        try:
            # Heuristic: ms vs s timestamps
            ts = float(value)
            if ts > 1e12:
                ts /= 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(text.replace("Z", "+0000") if "%z" in fmt else text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def normalize_remote_modality(
    *,
    explicit: str | None = None,
    remote_flag: bool | None = None,
    location: str = "",
) -> str | None:
    if explicit:
        text = explicit.strip().lower().replace("-", "_").replace(" ", "_")
        if text in {"remote", "fully_remote", "work_from_home", "wfh"}:
            return "remote"
        if text in {"hybrid"}:
            return "hybrid"
        if text in {"on_site", "onsite", "in_office", "office"}:
            return "on_site"
    if remote_flag is True:
        return "remote"
    if remote_flag is False:
        return "on_site"
    loc = location.lower()
    if "remote" in loc and "hybrid" not in loc:
        return "remote"
    if "hybrid" in loc:
        return "hybrid"
    return None


def normalize_employment_type(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "fulltime": "full_time",
        "full_time": "full_time",
        "full": "full_time",
        "parttime": "part_time",
        "part_time": "part_time",
        "contract": "contract",
        "contracts": "contract",
        "contractor": "contract",
        "temporary": "temporary",
        "internship": "internship",
        "intern": "internship",
        "third_party": "contract",
    }
    return mapping.get(text, text or None)


def build_salary_range(
    data: dict[str, Any],
    *,
    range_keys: tuple[str, ...] = ("salary_range", "salary", "compensation"),
) -> tuple[str | None, dict[str, Any]]:
    """Return (display salary_range, structured salary metadata fragment)."""
    meta: dict[str, Any] = {}
    display = first_str(data, *range_keys) or None
    for min_key, max_key in (
        ("salary_min", "salary_max"),
        ("min_salary", "max_salary"),
        ("salaryMinimum", "salaryMaximum"),
    ):
        if data.get(min_key) is not None:
            meta["salary_min"] = data.get(min_key)
        if data.get(max_key) is not None:
            meta["salary_max"] = data.get(max_key)
    currency = first_str(data, "salary_currency", "currency")
    if currency:
        meta["salary_currency"] = currency
    period = first_str(data, "salary_period", "period")
    if period:
        meta["salary_period"] = period
    if not display and ("salary_min" in meta or "salary_max" in meta):
        lo = meta.get("salary_min")
        hi = meta.get("salary_max")
        cur = meta.get("salary_currency", "")
        if lo is not None and hi is not None:
            display = f"{cur}{lo}-{hi}".strip()
        elif lo is not None:
            display = f"{cur}{lo}+".strip()
        elif hi is not None:
            display = f"up to {cur}{hi}".strip()
        if display and meta.get("salary_period"):
            display = f"{display}/{meta['salary_period']}"
    return display, meta


def clean_description(value: Any) -> str:
    if value is None:
        return ""
    return strip_html(str(value))
