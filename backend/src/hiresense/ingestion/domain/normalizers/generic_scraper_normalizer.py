from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class GenericScraperNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("description_html", "")),
            "skills": [],
            "location": d.get("location", ""),
            "salary_range": None,
            "url": d.get("url", ""),
            "language": "en",
            "posted_date": None,
            "department": None,
        }
