from __future__ import annotations

from typing import Any, Protocol

from hiresense.ingestion.domain.models import RawJobListing


class JobNormalizer(Protocol):
    def normalize(self, raw: RawJobListing) -> dict[str, Any]: ...


class RemotiveNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        return {
            "title": d.get("title", ""),
            "company": d.get("company_name", ""),
            "description": d.get("description", ""),
            "skills": d.get("tags", []),
            "location": d.get("candidate_required_location", ""),
            "salary_range": d.get("salary") or None,
            "url": d.get("url", ""),
            "language": "en",
        }


class RemoteOKNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        salary_min = d.get("salary_min")
        salary_max = d.get("salary_max")
        salary_range = (
            f"${salary_min}-${salary_max}"
            if salary_min and salary_max
            else None
        )
        return {
            "title": d.get("position", ""),
            "company": d.get("company", ""),
            "description": d.get("description", ""),
            "skills": d.get("tags", []),
            "location": d.get("location", "Worldwide"),
            "salary_range": salary_range,
            "url": d.get("url", ""),
            "language": "en",
        }


class CSVNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        skills_str = d.get("skills", "")
        skills = (
            [s.strip() for s in skills_str.split(";")]
            if skills_str
            else []
        )
        return {
            "title": d.get("title", ""),
            "company": d.get("company", ""),
            "description": d.get("description", ""),
            "skills": skills,
            "location": d.get("location", ""),
            "salary_range": d.get("salary_range") or None,
            "url": d.get("url", ""),
            "language": "en",
        }
