from __future__ import annotations

from datetime import datetime, timezone

from hiresense.ingestion.domain.application_method import ApplicationMethod
from hiresense.ingestion.domain.cross_source_deduplicator import (
    canonical_listing_key,
    consolidate_cross_source_jobs,
)
from hiresense.ingestion.domain.models import NormalizedJob


def _job(
    job_id: str,
    *,
    title: str = "Backend Engineer",
    company: str = "Acme",
    source: str = "board",
    description: str = "Build APIs",
    posted_date: datetime | None = None,
    application_method: ApplicationMethod = ApplicationMethod.UNKNOWN,
) -> NormalizedJob:
    return NormalizedJob(
        id=job_id,
        title=title,
        company=company,
        description=description,
        source=source,
        source_type="api",
        url=f"https://example.test/{job_id}",
        posted_date=posted_date,
        application_method=application_method,
    )


def test_canonical_listing_key_ignores_case_punctuation_and_legal_company_suffixes() -> None:
    board = _job("board", title="Backend-Engineer", company="Acme, Inc.")
    portal = _job("portal", title="backend engineer", company="ACME")

    assert canonical_listing_key(board) == canonical_listing_key(portal)


def test_consolidate_cross_source_jobs_keeps_the_direct_application_listing() -> None:
    board = _job(
        "board",
        source="aggregator",
        posted_date=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    portal = _job(
        "portal",
        source="acme-careers",
        application_method=ApplicationMethod.ATS_FORM,
        posted_date=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )
    portal = portal.model_copy(update={"apply_url": "https://boards.greenhouse.io/acme/jobs/1"})

    consolidated = consolidate_cross_source_jobs([board, portal])
    assert len(consolidated) == 1
    assert consolidated[0].id == "portal"
    assert consolidated[0].application_method == ApplicationMethod.ATS_FORM
    also = consolidated[0].source_metadata.get("also_found_on") or []
    assert {entry["source"] for entry in also} == {"aggregator", "acme-careers"}


def test_consolidate_prefers_ats_tier_and_merges_richer_fields() -> None:
    indeed = _job(
        "indeed",
        source="indeed",
        description="short",
        posted_date=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )
    indeed = indeed.model_copy(update={"salary_range": "$150k"})
    yc = _job(
        "yc",
        source="yc_jobs",
        description="Much longer description with startup context",
        posted_date=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )
    yc = yc.model_copy(update={"equity_range": "0.1% – 0.25%"})
    consolidated = consolidate_cross_source_jobs([indeed, yc])
    assert len(consolidated) == 1
    assert consolidated[0].source == "yc_jobs"
    assert consolidated[0].salary_range == "$150k"
    assert consolidated[0].equity_range == "0.1% – 0.25%"
    assert consolidated[0].source_metadata["source_urls"]["indeed"]


def test_consolidate_cross_source_jobs_keeps_distinct_or_underspecified_listings() -> None:
    backend = _job("backend")
    designer = _job("designer", title="Product Designer")
    other_company = _job("other-company", company="Beta")
    no_company = _job("no-company", company="")

    assert consolidate_cross_source_jobs([backend, designer, other_company, no_company]) == [
        backend,
        designer,
        other_company,
        no_company,
    ]


def test_consolidate_cross_source_jobs_does_not_merge_same_source_openings() -> None:
    first_opening = _job("first", source="acme-careers")
    second_opening = _job("second", source="acme-careers")

    assert consolidate_cross_source_jobs([first_opening, second_opening]) == [
        first_opening,
        second_opening,
    ]
