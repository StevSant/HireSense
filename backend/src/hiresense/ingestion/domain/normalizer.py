from __future__ import annotations

from typing import Any, Protocol

from hiresense.ingestion.domain.date_parser import parse_iso_date
from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class JobNormalizer(Protocol):
    def normalize(self, raw: RawJobListing) -> dict[str, Any]: ...


class RemotiveNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        return {
            "title": d.get("title", ""),
            "company": d.get("company_name", ""),
            "description": strip_html(d.get("description", "")),
            "skills": d.get("tags", []),
            "location": d.get("candidate_required_location", ""),
            "salary_range": d.get("salary") or None,
            "url": d.get("url", ""),
            "language": "en",
            "posted_date": parse_iso_date(d.get("publication_date")),
        }


class CSVNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        skills_str = d.get("skills", "")
        skills = [s.strip() for s in skills_str.split(";")] if skills_str else []
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": strip_html(d.get("description", "")),
            "skills": skills,
            "location": d.get("location", ""),
            "salary_range": d.get("salary_range") or None,
            "url": d.get("url", ""),
            "language": "en",
        }
