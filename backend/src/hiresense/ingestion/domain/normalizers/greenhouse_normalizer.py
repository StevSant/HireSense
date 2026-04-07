from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class GreenhouseNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        location_obj = d.get("location")
        location = location_obj["name"] if isinstance(location_obj, dict) else ""
        departments = d.get("departments", [])
        department = departments[0]["name"] if departments else None
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("content", "")),
            "skills": [],
            "location": location,
            "salary_range": None,
            "url": d.get("absolute_url", ""),
            "language": "en",
            "posted_date": d.get("updated_at"),
            "department": department,
        }
