import pytest

from hiresense.scheduler.domain import JobDefinition
from hiresense.scheduler.infrastructure import ApschedulerRunner


class _Runner:
    def __init__(self):
        self.ran = []

    async def run(self, name):
        self.ran.append(name)
        return name


def _defs():
    async def noop():
        return []

    return [
        JobDefinition(
            name="cron_job", run=noop, cron="0 9 * * *", interval_hours=None, count_items=len
        ),
        JobDefinition(name="interval_job", run=noop, cron=None, interval_hours=24, count_items=len),
    ]


@pytest.mark.asyncio
async def test_start_registers_one_apscheduler_job_per_definition():
    job_runner = _Runner()
    runner = ApschedulerRunner(job_runner=job_runner, definitions=_defs())
    runner.start()
    try:
        assert runner.next_run_at("cron_job") is not None
        assert runner.next_run_at("interval_job") is not None
        assert runner.next_run_at("unknown") is None
    finally:
        runner.shutdown()


@pytest.mark.asyncio
async def test_trigger_now_delegates_to_job_runner():
    job_runner = _Runner()
    runner = ApschedulerRunner(job_runner=job_runner, definitions=_defs())
    await runner.trigger_now("cron_job")
    assert job_runner.ran == ["cron_job"]
