from datetime import datetime, timezone

from hiresense.scheduler.domain import JobRun, JobStatus


def test_job_run_roundtrips_status_and_duration():
    started = datetime(2026, 6, 21, 9, 0, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 6, 21, 9, 0, 2, tzinfo=timezone.utc)
    run = JobRun(
        job_name="autohunt_digest",
        started_at=started,
        finished_at=finished,
        status=JobStatus.SUCCESS,
        detail=None,
        items_affected=5,
        duration_seconds=2.0,
    )
    assert run.status is JobStatus.SUCCESS
    assert run.items_affected == 5
    assert run.duration_seconds == 2.0
    assert run.started_at == started
    assert run.finished_at == finished
