from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class SmartRecruitersNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        loc = d.get("location") or {}
        country = loc.get("country", "")
        parts = [loc.get("city", ""), loc.get("region", ""), country]
        place = ", ".join(p for p in parts if p)
        is_remote = bool(loc.get("remote"))
        if is_remote:
            remote_modality = "remote"
            location = f"{place} (Remote)" if place else "Remote"
        else:
            remote_modality = "on_site"
            location = place
        department = d.get("department") or {}
        # The postings list carries no description; jobAd text lives behind a
        # separate detail call. Keep the listing fields we have.
        return {
            "title": d.get("name", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("jobAd", "") or ""),
            "skills": [],
            "location": location,
            "salary_range": None,
            "url": d.get("public_url", ""),
            "language": "en",
            "posted_date": d.get("releasedDate") or d.get("createdOn"),
            "department": department.get("label"),
            "remote_modality": remote_modality,
            "countries": [country.upper()] if country else [],
        }
