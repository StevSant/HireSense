from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class GetOnBoardNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        attrs = d.get("attributes", {})
        links = d.get("links", {})
        relationships = d.get("relationships", {})
        description_parts = [
            attrs.get("description", ""),
            attrs.get("projects", ""),
            attrs.get("functions", ""),
        ]
        description = strip_html("\n".join(p for p in description_parts if p))
        min_salary = attrs.get("min_salary")
        max_salary = attrs.get("max_salary")
        currency = attrs.get("currency", "USD")
        salary_range = (
            f"{currency} {min_salary}-{max_salary}/mo"
            if min_salary and max_salary
            else None
        )
        posted_date = None
        published_at = attrs.get("published_at")
        if published_at:
            try:
                posted_date = datetime.fromtimestamp(published_at, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                pass
        countries = attrs.get("countries", []) or []
        remote = attrs.get("remote", False)
        remote_modality_raw = (attrs.get("remote_modality") or "").lower()
        # Getonbrd uses: "remote_local" (fully remote), "hybrid", "in_office".
        # Normalise to the three values the filter reasons about.
        if remote and remote_modality_raw != "hybrid":
            remote_modality = "remote"
        elif remote_modality_raw == "hybrid":
            remote_modality = "hybrid"
        else:
            remote_modality = "on_site"
        clean_countries = [c for c in countries if c and c.lower() != "remote"]
        if remote_modality == "remote" and not clean_countries:
            location = "Remote"
        elif remote_modality == "remote":
            location = f"{', '.join(clean_countries)} (Remote)"
        elif remote_modality == "hybrid":
            location = f"{', '.join(clean_countries)} (Hybrid)" if clean_countries else "Hybrid"
        else:
            location = ", ".join(clean_countries)
        tags = [
            tag_ref.get("id", "")
            for tag_ref in relationships.get("tags", {}).get("data", [])
            if tag_ref.get("id")
        ]
        category = attrs.get("category_name", "")
        if category and category not in tags:
            tags.append(category)
        latam_countries = (
            "Chile", "Colombia", "Mexico", "Argentina", "Peru", "Ecuador",
            "Venezuela", "Bolivia", "Uruguay", "Paraguay", "Costa Rica",
            "Guatemala", "Honduras", "El Salvador", "Nicaragua", "Panama",
            "Dominican Republic", "Cuba",
        )
        language = "es" if any(c in latam_countries for c in countries) else "en"
        return {
            "title": attrs.get("title", ""),
            "company": attrs.get("company_name", str(relationships.get("company", {}).get("data", {}).get("id", ""))),
            "description": description,
            "skills": tags,
            "location": location,
            "salary_range": salary_range,
            "url": links.get("public_url", ""),
            "language": language,
            "posted_date": posted_date,
            "remote_modality": remote_modality,
            "countries": clean_countries,
        }
