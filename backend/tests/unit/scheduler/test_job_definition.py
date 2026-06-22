import asyncio

from hiresense.scheduler.domain import JobDefinition, ScheduledJobView


def test_job_definition_holds_trigger_and_counter():
    async def run():
        return [1, 2, 3]

    d = JobDefinition(
        name="ingestion_fetch",
        run=run,
        cron="0 */6 * * *",
        interval_hours=None,
        count_items=len,
        default_enabled=True,
    )
    assert d.name == "ingestion_fetch"
    assert d.count_items(asyncio.run(d.run())) == 3
    assert d.cron == "0 */6 * * *"


def test_scheduled_job_view_allows_null_run_and_next():
    view = ScheduledJobView(
        name="autohunt_digest", cron="0 9 * * *", enabled=True, last_run=None, next_run_at=None
    )
    assert view.last_run is None
    assert view.next_run_at is None
