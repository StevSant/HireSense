from __future__ import annotations

from hiresense.ingestion.domain.source_capabilities import (
    SOURCE_CAPABILITY_REGISTRY,
    get_source_capabilities,
    list_source_capabilities,
    source_tier,
)
from hiresense.ingestion.domain.source_health import (
    SourceHealthStatus,
    SourceHealthTracker,
    SourceRunStats,
)


def test_registry_covers_new_sources() -> None:
    for name in ("dice", "crunchboard", "yc_jobs", "indeed", "wellfound", "glassdoor", "monster"):
        caps = get_source_capabilities(name)
        assert caps is not None
        assert caps.source == name
    assert len(list_source_capabilities()) == len(SOURCE_CAPABILITY_REGISTRY)


def test_source_tier_prefers_ats_over_aggregators() -> None:
    assert source_tier("greenhouse") < source_tier("yc_jobs") < source_tier("dice")
    assert source_tier("indeed") > source_tier("yc_jobs")


def test_health_tracker_records_success_and_failure() -> None:
    tracker = SourceHealthTracker()
    tracker.record_run(
        "dice",
        duration_ms=12.5,
        stats=SourceRunStats(jobs_discovered=3, jobs_created=2, success=True),
    )
    healthy = tracker.get("dice")
    assert healthy.status == SourceHealthStatus.HEALTHY
    assert healthy.jobs_created == 2
    assert healthy.last_success_at is not None

    tracker.record_run(
        "dice",
        duration_ms=9.0,
        stats=SourceRunStats(success=False, error="TimeoutError: boom"),
    )
    failing = tracker.get("dice")
    assert failing.status == SourceHealthStatus.FAILING
    assert failing.last_error == "TimeoutError: boom"


def test_health_degraded_on_partial_parse_failures() -> None:
    tracker = SourceHealthTracker()
    tracker.record_run(
        "yc_jobs",
        duration_ms=20.0,
        stats=SourceRunStats(jobs_discovered=1, parse_failures=2, success=True),
    )
    assert tracker.get("yc_jobs").status == SourceHealthStatus.DEGRADED
