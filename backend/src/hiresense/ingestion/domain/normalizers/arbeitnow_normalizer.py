from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class ArbeitnowNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        is_remote = bool(d.get("remote"))
        location = d.get("location", "")
        if is_remote:
            remote_modality = "remote"
            location = f"{location} (Remote)" if location else "Remote"
        else:
            remote_modality = "on_site"
        posted_date = None
        created_at = d.get("created_at")
        if isinstance(created_at, (int, float)):
            try:
                posted_date = datetime.fromtimestamp(created_at, tz=timezone.utc)
            except (ValueError, OSError):
                pass
        tags = d.get("tags") or []
        url = d.get("url", "")
        metadata: dict[str, Any] = {}
        # Arbeitnow's own `<listing>/apply` hop 302s straight to the employer's
        # ATS (verified against Greenhouse), so recording it lets the UI skip
        # the aggregator page entirely. The listing URL stays canonical because
        # the closure sweep probes it.
        if url:
            metadata["application_url"] = f"{url.rstrip('/')}/apply"
        return {
            "title": d.get("title", ""),
            "company": d.get("company_name", ""),
            "description": strip_html(d.get("description", "")),
            "skills": [t for t in tags if isinstance(t, str)],
            "location": location,
            "salary_range": None,
            "url": url,
            "language": "en",
            "posted_date": posted_date,
            "remote_modality": remote_modality,
            "source_metadata": metadata,
        }
