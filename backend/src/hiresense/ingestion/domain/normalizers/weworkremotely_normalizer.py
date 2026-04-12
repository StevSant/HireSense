from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class WeWorkRemotelyNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        title_raw = d.get("title", "")
        company, title = _split_title(title_raw)
        posted_date = None
        published = d.get("published", "")
        if published:
            try:
                posted_date = parsedate_to_datetime(published)
            except (ValueError, TypeError):
                pass
        region = d.get("region", "")
        location = region if region else "Remote"
        skills_raw = d.get("skills", "")
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw else []
        category = d.get("category", "")
        if category and category not in skills:
            skills.append(category)
        return {
            "title": title,
            "company": company,
            "description": strip_html(d.get("summary", "")),
            "skills": skills,
            "location": location,
            "salary_range": None,
            "url": d.get("link", ""),
            "language": "en",
            "posted_date": posted_date,
        }


def _split_title(title: str) -> tuple[str, str]:
    """Split 'Company: Job Title' into (company, title)."""
    if ": " in title:
        company, _, job_title = title.partition(": ")
        return company.strip(), job_title.strip()
    return "", title.strip()
