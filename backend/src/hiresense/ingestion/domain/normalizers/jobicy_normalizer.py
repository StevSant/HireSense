from __future__ import annotations

from datetime import datetime
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class JobicyNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        salary_min = d.get("annualSalaryMin") or d.get("salaryMin")
        salary_max = d.get("annualSalaryMax") or d.get("salaryMax")
        currency = d.get("salaryCurrency", "USD")
        salary_range = (
            f"{currency} {salary_min}-{salary_max}" if salary_min and salary_max else None
        )
        posted_date = None
        pub_date = d.get("pubDate")
        if pub_date:
            try:
                posted_date = datetime.fromisoformat(pub_date)
            except (ValueError, TypeError):
                pass
        return {
            "title": d.get("jobTitle", ""),
            "company": d.get("companyName", ""),
            "description": strip_html(d.get("jobDescription", "")),
            "skills": d.get("jobIndustry", []),
            "location": d.get("jobGeo", ""),
            "salary_range": salary_range,
            "url": d.get("url", ""),
            "language": "en",
            "posted_date": posted_date,
        }
