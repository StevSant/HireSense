from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing


class ThoughtworksNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        source_id = str(d.get("sourceSystemId") or raw.source_id)
        location_parts = [p for p in [d.get("location"), d.get("country")] if p]
        remote = bool(d.get("remoteEligible"))
        location = ", ".join(location_parts)
        if remote:
            location = f"{location} (Remote)" if location else "Remote"
        functions = d.get("jobFunctions") or []
        department = functions[0] if functions else d.get("role")
        return {
            "title": d.get("name") or d.get("role") or "",
            "company": d.get("company", "Thoughtworks"),
            "description": "",
            "skills": [],
            "location": location,
            "salary_range": None,
            "url": f"https://www.thoughtworks.com/careers/jobs/{source_id}",
            "language": "en",
            "posted_date": d.get("updatedAt"),
            "department": department,
            "remote_modality": "remote" if remote else "on_site",
            "countries": [d["country"]] if d.get("country") else [],
        }
