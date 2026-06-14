from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class RecruiteeNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        salary = d.get("salary") or {}
        salary_min = salary.get("min")
        salary_max = salary.get("max")
        currency = salary.get("currency", "")
        salary_range = (
            f"{currency} {salary_min}-{salary_max}".strip()
            if salary_min and salary_max
            else None
        )
        is_remote = bool(d.get("remote"))
        country = d.get("country_code", "")
        place = d.get("location") or ", ".join(
            p for p in (d.get("city", ""), country) if p
        )
        if is_remote:
            remote_modality = "remote"
            location = f"{place} (Remote)" if place else "Remote"
        else:
            remote_modality = "on_site"
            location = place
        description = strip_html(
            "\n".join(
                p for p in (d.get("description", ""), d.get("requirements", "")) if p
            )
        )
        tags = d.get("tags") or []
        skills = [t for t in tags if isinstance(t, str)]
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": description,
            "skills": skills,
            "location": location,
            "salary_range": salary_range,
            "url": d.get("careers_url") or d.get("careers_apply_url", ""),
            "language": "en",
            "posted_date": d.get("published_at") or d.get("created_at"),
            "department": d.get("department"),
            "remote_modality": remote_modality,
            "countries": [country.upper()] if country else [],
        }
