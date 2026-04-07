from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class LeverNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        categories = d.get("categories") or {}
        created_at_ms = d.get("createdAt")
        if created_at_ms is not None:
            posted_date = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc).isoformat()
        else:
            posted_date = None
        return {
            "title": d.get("text", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("description", "")),
            "skills": [],
            "location": categories.get("location", ""),
            "salary_range": None,
            "url": d.get("hostedUrl", ""),
            "language": "en",
            "posted_date": posted_date,
            "department": categories.get("team"),
        }
