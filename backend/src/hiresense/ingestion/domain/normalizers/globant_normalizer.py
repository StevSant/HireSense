from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing


class GlobantNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        source_id = str(d.get("jobReqId") or raw.source_id)
        location_parts = [p for p in [d.get("location"), d.get("country")] if p]
        areas = d.get("area") or []
        department = None
        if isinstance(areas, list) and areas:
            first = areas[0]
            if isinstance(first, dict):
                department = first.get("label")
            else:
                department = str(first)
        return {
            "title": d.get("jobTitle") or "",
            "company": d.get("company", "Globant"),
            "description": d.get("jobDescription") or "",
            "skills": [],
            "location": ", ".join(location_parts),
            "salary_range": None,
            "url": f"https://career.globant.com/?id={source_id}",
            "language": "en",
            "posted_date": d.get("createdDateTime"),
            "department": department,
            "remote_modality": None,
            "countries": [d["country"]] if d.get("country") else [],
        }
