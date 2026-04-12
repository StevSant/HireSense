from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class HimalayasNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        min_salary = d.get("minSalary")
        max_salary = d.get("maxSalary")
        currency = d.get("currency", "USD")
        salary_range = (
            f"{currency} {min_salary}-{max_salary}"
            if min_salary and max_salary
            else None
        )
        posted_date = None
        pub_ts = d.get("pubDate")
        if pub_ts:
            try:
                if isinstance(pub_ts, (int, float)):
                    posted_date = datetime.fromtimestamp(pub_ts, tz=timezone.utc)
                else:
                    posted_date = datetime.fromisoformat(str(pub_ts).replace("Z", "+00:00"))
            except (ValueError, TypeError, OSError):
                pass
        categories = d.get("categories", []) + d.get("parentCategories", [])
        locations = d.get("locationRestrictions", [])
        location = ", ".join(locations) if locations else "Worldwide"
        return {
            "title": d.get("title", ""),
            "company": d.get("companyName", ""),
            "description": strip_html(d.get("description", "")),
            "skills": categories,
            "location": location,
            "salary_range": salary_range,
            "url": d.get("applicationLink", ""),
            "language": "en",
            "posted_date": posted_date,
        }
