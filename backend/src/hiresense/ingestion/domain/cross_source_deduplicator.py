from __future__ import annotations

import re
import unicodedata
from datetime import timezone

from hiresense.ingestion.domain.application_method import ApplicationMethod
from hiresense.ingestion.domain.models import NormalizedJob

_NON_WORD = re.compile(r"[\W_]+", flags=re.UNICODE)
_LEGAL_COMPANY_SUFFIXES = frozenset({"co", "company", "corp", "corporation", "inc", "llc", "ltd"})


def _normalized_tokens(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value).casefold()
    return [token for token in _NON_WORD.sub(" ", normalized).split() if token]


def _canonical_company(company: str) -> str:
    tokens = _normalized_tokens(company)
    while len(tokens) > 1 and tokens[-1] in _LEGAL_COMPANY_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def canonical_listing_key(job: NormalizedJob) -> str | None:
    """Source-independent key for safely comparable company/title listings.

    This deliberately uses exact normalized company and title values rather
    than fuzzy similarity: a false consolidation can hide a real opening.
    Listings without either value remain independent because they do not carry
    enough evidence to establish an equivalence class.
    """
    company = _canonical_company(job.company)
    title = " ".join(_normalized_tokens(job.title))
    if not company or not title:
        return None
    return f"{company}:{title}"


def _representative_sort_key(job: NormalizedJob) -> tuple[bool, bool, float, int, int, str]:
    posted_date = job.posted_date
    if posted_date is not None and posted_date.tzinfo is None:
        posted_date = posted_date.replace(tzinfo=timezone.utc)
    posted_timestamp = posted_date.timestamp() if posted_date is not None else float("-inf")
    return (
        job.application_method != ApplicationMethod.ATS_FORM,
        not bool(job.apply_url),
        -posted_timestamp,
        -len(job.description),
        -len(job.skills),
        job.id,
    )


def consolidate_cross_source_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    """Collapse matching listings from different sources for a single feed.

    Per-source persistence identities stay untouched, preserving lifecycle and
    source-health behavior. At read time, a direct ATS form is preferred, then
    the newest and richest listing; ties are deterministic by id. A group seen
    from only one source is left intact to avoid treating distinct openings on
    the same board as duplicates.
    """
    grouped: dict[str, list[NormalizedJob]] = {}
    independent: list[NormalizedJob] = []
    for job in jobs:
        key = canonical_listing_key(job)
        if key is None:
            independent.append(job)
        else:
            grouped.setdefault(key, []).append(job)

    representatives: dict[str, NormalizedJob] = {}
    for key, group in grouped.items():
        if len({job.source for job in group}) < 2:
            continue
        representatives[key] = min(group, key=_representative_sort_key)

    consolidated: list[NormalizedJob] = []
    emitted: set[str] = set()
    for job in jobs:
        key = canonical_listing_key(job)
        if key is None:
            consolidated.append(job)
        elif key not in representatives:
            consolidated.append(job)
        elif key not in emitted:
            consolidated.append(representatives[key])
            emitted.add(key)
    return consolidated
