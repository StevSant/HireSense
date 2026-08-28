from __future__ import annotations

import pytest
from pydantic import ValidationError

from hiresense.ingestion.domain.models import RawJobListing, SourceFetchMetadata
from hiresense.ingestion.domain.source_health import SourceHealthTracker, SourceRunStats


def test_raw_job_listing_rejects_empty_identity() -> None:
    with pytest.raises(ValidationError):
        RawJobListing(source=" ", source_id="job-1", raw_data={"title": "x"})


def test_raw_job_listing_carries_fetch_metadata() -> None:
    listing = RawJobListing(
        source="board",
        source_id="job-1",
        raw_data={"title": "x"},
        fetch_metadata=SourceFetchMetadata(
            complete=False,
            pages_fetched=2,
            parser_confidence=0.6,
            warnings=["truncated"],
        ),
    )
    assert listing.fetch_metadata.complete is False
    assert listing.fetch_metadata.parser_confidence == 0.6


def test_health_marks_incomplete_low_confidence_fetch_degraded() -> None:
    tracker = SourceHealthTracker()
    tracker.record_run(
        "board",
        duration_ms=10,
        stats=SourceRunStats(fetch_complete=False, parser_confidence=0.6),
    )
    health = tracker.get("board")
    assert health.status.value == "degraded"
    assert health.last_fetch_complete is False
