from __future__ import annotations

import re
import unicodedata
from datetime import timezone

from hiresense.ingestion.domain.application_method import ApplicationMethod
from hiresense.ingestion.domain.models import NormalizedJob
from hiresense.ingestion.domain.source_capabilities import source_tier

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


def _provenance_entry(job: NormalizedJob) -> dict:
    return {
        "source": job.source,
        "url": job.url,
        "posted_date": job.posted_date.isoformat() if job.posted_date else None,
        "job_id": job.id,
        "apply_url": job.apply_url,
    }


def _merge_representative(group: list[NormalizedJob], winner: NormalizedJob) -> NormalizedJob:
    """Prefer the winner identity but keep the richest explicit field values.

    Field merge rules (when winner is missing a value, take from the richest peer):
    longer description, more skills, non-empty salary/equity/employment_type,
    remote_modality, visa facts. Provenance of every peer is recorded under
    source_metadata.also_found_on without inventing missing values.
    """
    merged = winner.model_copy(deep=True)
    meta = dict(merged.source_metadata or {})
    also_found = [_provenance_entry(j) for j in group]
    meta["also_found_on"] = also_found
    source_urls = {j.source: j.url for j in group if j.url}
    if source_urls:
        meta["source_urls"] = source_urls

    for peer in group:
        if peer.id == winner.id:
            continue
        if len(peer.description) > len(merged.description):
            merged.description = peer.description
        if len(peer.skills) > len(merged.skills):
            merged.skills = list(peer.skills)
        if not merged.salary_range and peer.salary_range:
            merged.salary_range = peer.salary_range
        if not merged.equity_range and peer.equity_range:
            merged.equity_range = peer.equity_range
        if not merged.employment_type and peer.employment_type:
            merged.employment_type = peer.employment_type
        if not merged.remote_modality and peer.remote_modality:
            merged.remote_modality = peer.remote_modality
        if (
            merged.requires_existing_work_authorization is None
            and peer.requires_existing_work_authorization is not None
        ):
            merged.requires_existing_work_authorization = peer.requires_existing_work_authorization
        if (
            merged.visa_sponsorship_available is None
            and peer.visa_sponsorship_available is not None
        ):
            merged.visa_sponsorship_available = peer.visa_sponsorship_available
        # Prefer a direct apply URL when the winner lacks one.
        if not merged.apply_url and peer.apply_url:
            merged.apply_url = peer.apply_url
            merged.application_method = peer.application_method
            merged.ats_type = peer.ats_type
        # Merge peer metadata keys that winner lacks (never overwrite).
        for key, value in (peer.source_metadata or {}).items():
            if key in ("also_found_on", "source_urls"):
                continue
            if key not in meta and value is not None:
                meta[key] = value

    merged.source_metadata = meta
    return merged


def _representative_sort_key(job: NormalizedJob) -> tuple:
    posted_date = job.posted_date
    if posted_date is not None and posted_date.tzinfo is None:
        posted_date = posted_date.replace(tzinfo=timezone.utc)
    posted_timestamp = posted_date.timestamp() if posted_date is not None else float("-inf")
    return (
        job.application_method != ApplicationMethod.ATS_FORM,
        not bool(job.apply_url),
        source_tier(job.source),
        -posted_timestamp,
        -len(job.description),
        -len(job.skills),
        job.id,
    )


def consolidate_cross_source_jobs(jobs: list[NormalizedJob]) -> list[NormalizedJob]:
    """Collapse matching listings from different sources for a single feed.

    Per-source persistence identities stay untouched, preserving lifecycle and
    source-health behavior. At read time, a direct ATS form is preferred, then
    lower source-tier (company ATS / YC over aggregators), then the newest and
    richest listing; ties are deterministic by id. A group seen from only one
    source is left intact to avoid treating distinct openings on the same board
    as duplicates. Provenance of collapsed peers is attached to the representative.
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
        winner = min(group, key=_representative_sort_key)
        representatives[key] = _merge_representative(group, winner)

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
