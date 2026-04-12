from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing


class LinkedInNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": "",
            "skills": [],
            "location": d.get("location", ""),
            "salary_range": None,
            "url": d.get("url", ""),
            "language": "en",
            "posted_date": None,
        }
