from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class TheMuseNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        company = (d.get("company") or {}).get("name", "")
        locations = [
            loc.get("name", "") for loc in (d.get("locations") or []) if loc.get("name")
        ]
        location = ", ".join(locations)
        is_remote = any("remote" in loc.lower() for loc in locations)
        if is_remote:
            remote_modality = "remote"
        elif locations:
            remote_modality = "on_site"
        else:
            remote_modality = None
        categories = [
            c.get("name", "") for c in (d.get("categories") or []) if c.get("name")
        ]
        levels = [
            lv.get("name", "") for lv in (d.get("levels") or []) if lv.get("name")
        ]
        skills = categories + levels
        refs = d.get("refs") or {}
        return {
            "title": d.get("name", ""),
            "company": company,
            "description": strip_html(d.get("contents", "") or ""),
            "skills": skills,
            "location": location,
            "salary_range": None,
            "url": refs.get("landing_page", ""),
            "language": "en",
            "posted_date": d.get("publication_date"),
            "remote_modality": remote_modality,
        }
