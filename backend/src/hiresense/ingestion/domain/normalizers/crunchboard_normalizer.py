from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.models import RawJobListing
from hiresense.ingestion.domain.normalizers._import_fields import (
    clean_description,
    normalize_employment_type,
    normalize_remote_modality,
    parse_posted_date,
)
from hiresense.ingestion.domain.normalizers.crunchboard_title import parse_crunchboard_title


class CrunchBoardNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        raw_title = d.get("title") or ""
        title, company, location = parse_crunchboard_title(raw_title)
        description = clean_description(d.get("summary") or "")
        remote_modality = normalize_remote_modality(location=location or description)
        employment = None
        # Job type sometimes appears as "Job Type: Full-time" in the description snippet.
        lower_desc = description.lower()
        for needle, value in (
            ("full-time", "full_time"),
            ("full time", "full_time"),
            ("part-time", "part_time"),
            ("contract", "contract"),
            ("internship", "internship"),
        ):
            if needle in lower_desc:
                employment = normalize_employment_type(value)
                break
        tags = d.get("tags") or []
        skills = [t for t in tags if isinstance(t, str)]
        meta: dict[str, Any] = {}
        if d.get("guid"):
            meta["guid"] = d["guid"]
        return {
            "title": title or raw_title,
            "company": company or "Unknown",
            "description": description,
            "skills": skills,
            "location": location,
            "salary_range": None,
            "employment_type": employment,
            "equity_range": None,
            "url": d.get("link") or "",
            "language": "en",
            "posted_date": parse_posted_date(d.get("published")),
            "remote_modality": remote_modality,
            "categories": skills[:],
            "source_metadata": meta,
        }
