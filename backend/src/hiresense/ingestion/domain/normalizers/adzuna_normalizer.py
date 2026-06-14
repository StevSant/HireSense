from __future__ import annotations

from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing

# Per-country salary currency (Adzuna results omit the currency symbol).
_CURRENCY = {
    "mx": "MXN", "br": "BRL", "ar": "ARS", "us": "USD", "gb": "GBP",
    "de": "EUR", "fr": "EUR", "es": "EUR", "it": "EUR", "nl": "EUR",
    "ca": "CAD", "au": "AUD", "in": "INR",
}


class AdzunaNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        country = d.get("country", "")
        salary_min = d.get("salary_min")
        salary_max = d.get("salary_max")
        currency = _CURRENCY.get(country, "")
        salary_range = None
        if salary_min and salary_max:
            salary_range = f"{currency} {int(salary_min)}-{int(salary_max)}".strip()
        location_obj = d.get("location") or {}
        location = location_obj.get("display_name", "")
        area = location_obj.get("area") or []
        # Adzuna has no explicit remote flag — only assert "remote" when the
        # text says so; otherwise leave unknown (None) rather than guessing.
        haystack = f"{d.get('title', '')} {location}".lower()
        remote_modality = "remote" if "remote" in haystack else None
        category = (d.get("category") or {}).get("label", "")
        return {
            "title": d.get("title", ""),
            "company": (d.get("company") or {}).get("display_name", ""),
            "description": strip_html(d.get("description", "")),
            "skills": [category] if category else [],
            "location": location,
            "salary_range": salary_range,
            "url": d.get("redirect_url", ""),
            "language": "en",
            "posted_date": d.get("created"),
            "remote_modality": remote_modality,
            "countries": [area[0]] if area else ([country.upper()] if country else []),
        }
