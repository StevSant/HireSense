from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class HimalayasNormalizer:
    @staticmethod
    def _parse_ts(value: Any) -> datetime | None:
        """Himalayas timestamps arrive as unix seconds (int/float) or, rarely,
        an ISO string. Return a tz-aware UTC datetime, or None if unparseable."""
        if not value:
            return None
        try:
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(value, tz=timezone.utc)
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError, OSError):
            return None

    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        min_salary = d.get("minSalary")
        max_salary = d.get("maxSalary")
        currency = d.get("currency", "USD")
        salary_range = (
            f"{currency} {min_salary}-{max_salary}" if min_salary and max_salary else None
        )
        posted_date = self._parse_ts(d.get("pubDate"))
        # Himalayas' API declares a per-job expiry; captured here so the
        # revalidation sweep can close the listing on expiry (its public page
        # blocks URL probes with a 403).
        expiry_date = self._parse_ts(d.get("expiryDate"))
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
            "expiry_date": expiry_date,
        }
