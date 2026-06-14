from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class WorkableNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        telecommuting = bool(d.get("telecommuting"))
        country = d.get("country", "")
        parts = [d.get("city", ""), d.get("state", ""), country]
        place = ", ".join(p for p in parts if p)
        if telecommuting:
            remote_modality = "remote"
            location = f"{place} (Remote)" if place else "Remote"
        else:
            remote_modality = "on_site"
            location = place
        description = strip_html(
            "\n".join(
                p
                for p in (
                    d.get("description", ""),
                    d.get("requirements", ""),
                    d.get("benefits", ""),
                )
                if p
            )
        )
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": description,
            "skills": [],
            "location": location,
            "salary_range": None,
            "url": d.get("url") or d.get("shortlink") or d.get("application_url", ""),
            "language": "en",
            "posted_date": d.get("published_on") or d.get("created_at"),
            "department": d.get("department"),
            "remote_modality": remote_modality,
            "countries": [country] if country else [],
        }
