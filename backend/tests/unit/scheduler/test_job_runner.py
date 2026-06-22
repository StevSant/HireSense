from datetime import datetime, timezone

import pytest

from hiresense.ingestion.domain import IngestionCooldownError
from hiresense.scheduler.domain import JobDefinition, JobRunner, JobStatus


class _RunRepo:
    def __init__(self):
        self.recorded = []

    def record(self, run):
        self.recorded.append(run)
        return run

    def recent(self, job_name, limit):
        return [r for r in self.recorded if r.job_name == job_name][:limit]

    def latest(self, job_name):
        runs = [r for r in self.recorded if r.job_name == job_name]
        return runs[-1] if runs else None


class _ToggleRepo:
    def __init__(self, enabled=True):
        self._enabled = enabled

    def is_enabled(self, job_name, default):
        return self._enabled

    def set_enabled(self, job_name, enabled):
        self._enabled = enabled

    def all_states(self):
        return {}


def _clock_seq(*times):
    it = iter(times)
    return lambda: next(it)


def _runner(defn, run_repo=None, toggle_repo=None, clock=None):
    return JobRunner(
        definitions=[defn],
        run_repo=run_repo or _RunRepo(),
        toggle_repo=toggle_repo or _ToggleRepo(),
        clock=clock,
    )


def _defn(run, count_items=len, default_enabled=True):
    return JobDefinition(
        name="job", run=run, cron="0 9 * * *", interval_hours=None,
        count_items=count_items, default_enabled=default_enabled,
    )


@pytest.mark.asyncio
async def test_success_records_count_and_duration():
    async def run():
        return [1, 2]

    t0 = datetime(2026, 6, 21, 9, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 6, 21, 9, 0, 3, tzinfo=timezone.utc)
    repo = _RunRepo()
    runner = _runner(_defn(run), run_repo=repo, clock=_clock_seq(t0, t1))
    result = await runner.run("job")
    assert result.status is JobStatus.SUCCESS
    assert result.items_affected == 2
    assert result.duration_seconds == 3.0
    assert repo.recorded[-1].status is JobStatus.SUCCESS


@pytest.mark.asyncio
async def test_disabled_job_is_skipped_without_running():
    ran = {"called": False}

    async def run():
        ran["called"] = True
        return []

    runner = _runner(_defn(run), toggle_repo=_ToggleRepo(enabled=False))
    result = await runner.run("job")
    assert result.status is JobStatus.SKIPPED
    assert result.duration_seconds == 0.0
    assert ran["called"] is False


@pytest.mark.asyncio
async def test_cooldown_is_skipped_not_failure():
    async def run():
        raise IngestionCooldownError(retry_after=60)

    result = await _runner(_defn(run)).run("job")
    assert result.status is JobStatus.SKIPPED


@pytest.mark.asyncio
async def test_unexpected_error_is_recorded_as_failure_and_swallowed():
    async def run():
        raise RuntimeError("boom")

    result = await _runner(_defn(run)).run("job")
    assert result.status is JobStatus.FAILURE
    assert "boom" in (result.detail or "")


@pytest.mark.asyncio
async def test_unknown_job_name_records_failure_not_raises():
    async def run():
        return []

    runner = _runner(_defn(run))
    result = await runner.run("does_not_exist")
    assert result.status is JobStatus.FAILURE
    assert "does_not_exist" in (result.detail or "")
