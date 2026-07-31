from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class WorkdayNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        detail = d.get("detail") or {}
        posting = detail.get("jobPostingInfo") or {}
        location = (
            d.get("locationsText") or posting.get("location") or posting.get("locationName") or ""
        )
        description = (
            posting.get("jobDescription")
            or posting.get("jobPostingDescription")
            or d.get("description")
            or ""
        )
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": strip_html(description),
            "skills": [],
            "location": location,
            "salary_range": None,
            "url": posting.get("externalUrl") or d.get("careers_url") or "",
            "language": "en",
            "posted_date": d.get("postedOn") or posting.get("startDate"),
            "department": posting.get("jobFamily") or posting.get("jobFamilyGroup"),
        }
