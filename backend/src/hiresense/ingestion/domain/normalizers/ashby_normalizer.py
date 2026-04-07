from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class AshbyNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        return {
            "title": d["title"],
            "company": d["company"],
            "description": strip_html(d["descriptionHtml"]),
            "skills": [],
            "location": d.get("location", ""),
            "salary_range": None,
            "url": d["jobUrl"],
            "language": "en",
            "posted_date": d.get("publishedAt"),
            "department": d.get("departmentName"),
        }
