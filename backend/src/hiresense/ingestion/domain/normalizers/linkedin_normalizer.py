from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.date_parser import parse_iso_date
from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class LinkedInNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("description", "")),
            "skills": [],
            "location": d.get("location", ""),
            "salary_range": None,
            "url": d.get("url", ""),
            "language": "en",
            "posted_date": parse_iso_date(d.get("posted_date")),
            "department": d.get("job_function") or None,
            "categories": [c for c in [d.get("seniority"), d.get("employment_type")] if c],
        }
