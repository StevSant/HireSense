from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hiresense.ingestion.domain import (
    IngestionRunSummary,
    JobClosureReason,
    JobHistoryEvent,
    JobHistoryEventType,
)


def test_event_defaults_to_empty_diff_and_no_reason():
    event = JobHistoryEvent(
        job_id="job-1",
        event=JobHistoryEventType.INSERTED,
        occurred_at=datetime.now(timezone.utc),
    )
    assert event.changed_fields == {}
    assert event.reason is None


def test_event_is_frozen():
    event = JobHistoryEvent(
        job_id="job-1",
        event=JobHistoryEventType.CLOSED,
        reason=JobClosureReason.PROBE_404,
        occurred_at=datetime.now(timezone.utc),
    )
    with pytest.raises(Exception):
        event.job_id = "job-2"


def test_enums_serialise_to_their_stored_string_values():
    assert JobHistoryEventType.REOPENED.value == "reopened"
    assert JobClosureReason.DEAD_END_REDIRECT.value == "dead_end_redirect"
    assert JobClosureReason.SNAPSHOT_DISAPPEARANCE.value == "snapshot_disappearance"
    assert JobClosureReason.CLOSED_MARKER.value == "closed_marker"


def test_run_summary_counts_default_to_zero():
    summary = IngestionRunSummary(
        id="run-1",
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        trigger="fetch",
        status="running",
    )
    assert (summary.inserted, summary.updated, summary.reopened, summary.closed) == (0, 0, 0, 0)
