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


# A real location / work-mode tag is short ("Berlin, Germany", "100% Remote
# (Global)", "ONSITE & Remote"). Header segments longer than this are almost
# always description prose that merely *mentions* a keyword like "remote" — they
# must never be classified as a location, or the whole blurb leaks into the
# location field (which broke the tracking table).
_MAX_LOCATION_LEN = 60

# Markers that strongly suggest a part is describing a *location* or
# *work-mode*, not a role title. Used to disambiguate ambiguous HN headers
# like "Company | Berlin, Germany | ONSITE & Remote".
_LOCATION_KEYWORDS = (
    "remote",
    "onsite",
    "on-site",
    "on site",
    "hybrid",
    "anywhere",
    "worldwide",
    "global",
    "us only",
    "us-only",
    "eu only",
    "eu-only",
)

# Words that signal a part *is* a role title (e.g. "Senior Engineer",
# "Backend Developer"). Used to win the tie against location detection.
_ROLE_KEYWORDS = (
    "engineer",
    "developer",
    "designer",
    "manager",
    "lead",
    "intern",
    "scientist",
    "analyst",
    "architect",
    "consultant",
    "researcher",
    "product",
    "founding",
    "principal",
    "head of",
    "director",
    "specialist",
    "writer",
    "marketer",
    "ops",
    "sre",
    "devops",
    "platform",
    "frontend",
    "front-end",
    "backend",
    "back-end",
    "fullstack",
    "full-stack",
    "full stack",
    "mobile",
    "ios",
    "android",
    "qa",
    "support",
    "sales",
)

# US state codes after a comma — strong "this is a US city" signal.
_US_STATE_CODES = (
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO "
    "MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY"
).split()


def _looks_like_role(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _ROLE_KEYWORDS)


def _looks_like_location(text: str) -> bool:
    """True if `text` reads as a place / work-mode rather than a role.

    Heuristics, ordered by strength:
      * obvious work-mode keywords (remote / hybrid / onsite / worldwide …)
      * "<word>, <US state code>" pattern (e.g. "St Paul, MN")
      * comma-separated multi-region list and no role keyword present
    """
    lower = text.lower().strip()
    if not lower or len(lower) > _MAX_LOCATION_LEN:
        return False
    if any(kw in lower for kw in _LOCATION_KEYWORDS):
        return True
    parts = [p.strip() for p in text.split(",")]
    if any(p in _US_STATE_CODES for p in parts):
        return not _looks_like_role(text)
    if text.count(",") >= 1 and not _looks_like_role(text):
        return True
    return False


_URL_PATTERN = re.compile(r"^https?://", re.I)

# Things that are *never* a job title — pure employment type / work mode
# strings that some HN postings drop straight after the company name.
_EMPLOYMENT_TYPE_NORMALISED = frozenset(
    {
        "full time",
        "full-time",
        "fulltime",
        "part time",
        "part-time",
        "parttime",
        "contract",
        "contractor",
        "freelance",
        "freelancer",
        "permanent",
        "temporary",
        "internship",
        "remote",
        "onsite",
        "on-site",
        "hybrid",
        "multiple roles",
        "multiple positions",
        "various roles",
    }
)


def _looks_like_url(text: str) -> bool:
    return bool(_URL_PATTERN.match(text.strip()))


def _is_pure_employment_marker(text: str) -> bool:
    """True if the whole string is a work-mode/employment-type tag.

    Examples: "Full Time", "Part-time", "REMOTE", "Multiple roles". These
    shouldn't be promoted to a title via the fallback, but they're fine to
    classify into location / mode through `_classify_extra`.
    """
    normalised = re.sub(r"\s+", " ", text.strip().lower())
    return normalised in _EMPLOYMENT_TYPE_NORMALISED


def _classify_extra(part: str, current: dict[str, str | None]) -> None:
    """Slot a free-form extra field into location / salary based on shape."""
    lower = part.lower()
    if len(part) <= _MAX_LOCATION_LEN and any(kw in lower for kw in _LOCATION_KEYWORDS):
        loc = current["location"] or ""
        current["location"] = f"{loc} ({part})" if loc else part
        return
    if re.search(r"\$|€|£|\dk", lower):
        current["salary"] = part


def _parse_hn_comment(html: str) -> dict[str, str | None]:
    """Parse the pipe-delimited header of an HN 'Who is Hiring?' comment."""
    text = strip_html(html)
    lines = text.strip().split("\n")
    result: dict[str, str | None] = {
        "company": "",
        "title": "",
        "location": "",
        "salary": None,
        "description": "",
    }
    if not lines:
        return result
    header = lines[0]
    parts = [p.strip() for p in header.split("|") if p.strip()]
    if not parts:
        return result

    result["company"] = parts[0]

    # parts[1:] can be in any of these orderings observed on HN:
    #   role | location | mode | salary
    #   location | role | mode | salary
    #   location | mode (no role at all — role described in the body)
    # We pick whichever remaining part most looks like a role for `title`,
    # treat the most location-y as `location`, and let the rest fall through
    # to the salary / work-mode classifier.
    remaining = parts[1:]
    role_idx: int | None = next(
        (i for i, p in enumerate(remaining) if _looks_like_role(p)),
        None,
    )
    if role_idx is not None:
        result["title"] = remaining.pop(role_idx)

    location_idx: int | None = next(
        (i for i, p in enumerate(remaining) if _looks_like_location(p)),
        None,
    )
    if location_idx is not None:
        result["location"] = remaining.pop(location_idx)
    elif remaining and not result["title"]:
        # Conservative fallback: nothing looks like a role *or* a location,
        # so treat the next non-garbage part as the title. URLs and pure
        # employment-type markers ("Full Time", "Part-time") are never a
        # title — those continue through to _classify_extra.
        fallback_idx: int | None = next(
            (
                i
                for i, p in enumerate(remaining)
                if not _looks_like_url(p) and not _is_pure_employment_marker(p)
            ),
            None,
        )
        if fallback_idx is not None:
            result["title"] = remaining.pop(fallback_idx)

    for extra in remaining:
        _classify_extra(extra, result)

    result["description"] = "\n".join(lines[1:]).strip()
    return result
