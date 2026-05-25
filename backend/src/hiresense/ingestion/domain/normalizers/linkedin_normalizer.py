from __future__ import annotations

from datetime import datetime
from typing import Any

from hiresense.ingestion.domain.models import RawJobListing


class LinkedInNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        posted_date = self._parse_date(d.get("posted_date", ""))
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": d.get("description", ""),
            "skills": [],
            "location": d.get("location", ""),
            "salary_range": None,
            "url": d.get("url", ""),
            "language": "en",
            "posted_date": posted_date,
            "department": d.get("job_function") or None,
            "categories": [c for c in [d.get("seniority"), d.get("employment_type")] if c],
        }

    @staticmethod
    def _parse_date(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
