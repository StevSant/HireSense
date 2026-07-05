import pytest

from hiresense.ingestion.domain import IngestionCooldownError
from hiresense.scheduler.domain import JobDefinition, JobRunner, JobStatus


class _RunRepo:
    def __init__(self):
        self.recorded = []

    def record(self, run):
        self.recorded.append(run)
        return run

    def recent(self, n, limit):
        return []

    def latest(self, n):
        return None


class _ToggleRepo:
    def is_enabled(self, name, default):
        return True

    def set_enabled(self, name, enabled): ...

    def all_states(self):
        return {}


class _Notifier:
    def __init__(self, raise_exc=None):
        self.calls = []
        self._raise = raise_exc

    async def notify_job_failure(self, job_name, detail):
        self.calls.append((job_name, detail))
        if self._raise:
            raise self._raise
        return True


def _defn(run):
    return JobDefinition(
        name="job", run=run, cron="0 9 * * *", interval_hours=None, count_items=len
    )


def _runner(defn, notifier):
    return JobRunner(
        definitions=[defn],
        run_repo=_RunRepo(),
        toggle_repo=_ToggleRepo(),
        failure_notifier=notifier,
    )


@pytest.mark.asyncio
async def test_failure_invokes_notifier():
    async def run():
        raise RuntimeError("boom")

    notifier = _Notifier()
    result = await _runner(_defn(run), notifier).run("job")
    assert result.status is JobStatus.FAILURE
    assert notifier.calls == [("job", "boom")]


@pytest.mark.asyncio
async def test_notifier_error_is_swallowed():
    async def run():
        raise RuntimeError("boom")

    notifier = _Notifier(raise_exc=RuntimeError("notify failed"))
    # Must not raise; failure still recorded.
    result = await _runner(_defn(run), notifier).run("job")
    assert result.status is JobStatus.FAILURE


@pytest.mark.asyncio
async def test_success_does_not_notify():
    async def run():
        return [1]

    notifier = _Notifier()
    result = await _runner(_defn(run), notifier).run("job")
    assert result.status is JobStatus.SUCCESS
    assert notifier.calls == []


@pytest.mark.asyncio
async def test_cooldown_skip_does_not_notify():
    async def run():
        raise IngestionCooldownError(retry_after=60)

    notifier = _Notifier()
    result = await _runner(_defn(run), notifier).run("job")
    assert result.status is JobStatus.SKIPPED
    assert notifier.calls == []


@pytest.mark.asyncio
async def test_unknown_job_does_not_notify():
    async def run():
        return [1]

    notifier = _Notifier()
    result = await _runner(_defn(run), notifier).run("does_not_exist")
    assert result.status is JobStatus.FAILURE
    assert notifier.calls == []
