from __future__ import annotations

from urllib.parse import urlparse

from hiresense.ingestion.domain.application_classification import ApplicationClassification
from hiresense.ingestion.domain.application_method import ApplicationMethod
from hiresense.ingestion.domain.ats_platform import AtsPlatform

# Host suffixes that uniquely identify a known ATS. Matched against the URL host
# with endswith(), so every subdomain is covered (e.g. job-boards.greenhouse.io,
# boards.eu.greenhouse.io, jobs.lever.co, company.recruitee.com).
_ATS_HOST_SUFFIXES: dict[str, AtsPlatform] = {
    "greenhouse.io": AtsPlatform.GREENHOUSE,
    "lever.co": AtsPlatform.LEVER,
    "ashbyhq.com": AtsPlatform.ASHBY,
    "workable.com": AtsPlatform.WORKABLE,
    "smartrecruiters.com": AtsPlatform.SMARTRECRUITERS,
    "recruitee.com": AtsPlatform.RECRUITEE,
}


def _coerce_platform(platform: str | None) -> AtsPlatform | None:
    """A portal's configured `platform` string → AtsPlatform, if recognised."""
    if not platform:
        return None
    try:
        return AtsPlatform(platform.strip().lower())
    except ValueError:
        return None


def _detect_from_url(url: str) -> AtsPlatform | None:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return None
    for suffix, platform in _ATS_HOST_SUFFIXES.items():
        if host == suffix or host.endswith("." + suffix):
            return platform
    return None


def classify_application(
    url: str | None, *, platform: str | None = None
) -> ApplicationClassification:
    """Classify how a job is applied to from its URL (and optional portal platform).

    `platform` (authoritative for portal-sourced jobs) wins over URL sniffing;
    board-sourced jobs pass platform=None and are classified by URL host. See
    the Phase 0 design doc for the full rule.
    """
    ats = _coerce_platform(platform) or _detect_from_url(url or "")
    if ats is not None:
        return ApplicationClassification(
            apply_url=url or None,
            application_method=ApplicationMethod.ATS_FORM,
            ats_type=ats.value,
        )
    if url:
        return ApplicationClassification(
            apply_url=None,
            application_method=ApplicationMethod.REDIRECT,
            ats_type=None,
        )
    return ApplicationClassification(
        apply_url=None,
        application_method=ApplicationMethod.UNKNOWN,
        ats_type=None,
    )
