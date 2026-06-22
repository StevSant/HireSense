from __future__ import annotations

import logging
from datetime import datetime
from functools import partial
from typing import Iterable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from hiresense.scheduler.domain import JobDefinition, JobRunner

logger = logging.getLogger(__name__)

# Allow a late fire to still run if the loop was busy/asleep briefly.
_MISFIRE_GRACE_SECONDS = 300


class ApschedulerRunner:
    """Drives JobRunner.run(name) on each definition's cadence via an
    AsyncIOScheduler. max_instances=1 + coalesce prevents overlapping/stacked
    runs."""

    def __init__(self, *, job_runner: JobRunner, definitions: Iterable[JobDefinition]) -> None:
        self._job_runner = job_runner
        self._definitions = list(definitions)
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        for defn in self._definitions:
            self._scheduler.add_job(
                partial(self._job_runner.run, defn.name),
                trigger=self._trigger(defn),
                id=defn.name,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=_MISFIRE_GRACE_SECONDS,
                replace_existing=True,
            )
        self._scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self._definitions))

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def next_run_at(self, name: str) -> datetime | None:
        job = self._scheduler.get_job(name)
        return job.next_run_time if job is not None else None

    async def trigger_now(self, name: str):
        return await self._job_runner.run(name)

    @staticmethod
    def _trigger(defn: JobDefinition):
        if defn.cron is not None:
            return CronTrigger.from_crontab(defn.cron)
        return IntervalTrigger(hours=defn.interval_hours)
