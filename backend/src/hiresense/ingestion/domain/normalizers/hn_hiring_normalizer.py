from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from hiresense.ingestion.domain.html_stripper import strip_html
from hiresense.ingestion.domain.models import RawJobListing


class HNHiringNormalizer:
    def normalize(self, raw: RawJobListing) -> dict[str, Any]:
        d = raw.raw_data
        text = d.get("text", "")
        parsed = _parse_hn_comment(text)
        posted_date = None
        created_at = d.get("created_at", "")
        if created_at:
            try:
                posted_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        comment_id = d.get("id", d.get("thread_id", ""))
        url = f"https://news.ycombinator.com/item?id={comment_id}"
        return {
            "title": parsed["title"],
            "company": parsed["company"],
            "description": strip_html(parsed["description"]),
            "skills": [],
            "location": parsed["location"],
            "salary_range": parsed["salary"],
            "url": url,
            "language": "en",
            "posted_date": posted_date,
        }


def _parse_hn_comment(html: str) -> dict[str, str | None]:
    """Parse pipe-delimited header from an HN Who is Hiring comment."""
    text = strip_html(html)
    lines = text.strip().split("\n")
    result: dict[str, str | None] = {"company": "", "title": "", "location": "", "salary": None, "description": ""}
    if not lines:
        return result
    header = lines[0]
    parts = [p.strip() for p in header.split("|")]
    if len(parts) >= 1:
        result["company"] = parts[0]
    if len(parts) >= 2:
        result["title"] = parts[1]
    if len(parts) >= 3:
        result["location"] = parts[2]
    for part in parts[3:]:
        lower = part.lower()
        if any(kw in lower for kw in ("remote", "onsite", "on-site", "hybrid")):
            loc = result["location"]
            result["location"] = f"{loc} ({part})" if loc else part
        elif re.search(r"\$|€|£|\dk", lower):
            result["salary"] = part
    result["description"] = "\n".join(lines[1:]).strip()
    return result
