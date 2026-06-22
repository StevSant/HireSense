from __future__ import annotations

from typing import Iterable

from hiresense.scheduler.domain import JobDefinition, JobRun, ScheduledJobView
from hiresense.scheduler.domain.ports import JobRunRepository, JobToggleRepository


class SchedulerProvider:
    """Read/command surface for the scheduler API. Lists jobs (definitions +
    toggle + latest run + next fire), exposes run history, toggling, and manual
    run-now. Works whether or not the APScheduler runner was started."""

    def __init__(
        self,
        *,
        definitions: Iterable[JobDefinition],
        runner,
        run_repo: JobRunRepository,
        toggle_repo: JobToggleRepository,
    ) -> None:
        self._defs = list(definitions)
        self._runner = runner
        self._run_repo = run_repo
        self._toggle_repo = toggle_repo

    def list_jobs(self) -> list[ScheduledJobView]:
        return [
            ScheduledJobView(
                name=d.name,
                cron=d.cadence_label,
                enabled=self._toggle_repo.is_enabled(d.name, default=d.default_enabled),
                last_run=self._run_repo.latest(d.name),
                next_run_at=self._runner.next_run_at(d.name),
            )
            for d in self._defs
        ]

    def runs(self, name: str, limit: int) -> list[JobRun]:
        return self._run_repo.recent(name, limit)

    def set_enabled(self, name: str, enabled: bool) -> ScheduledJobView:
        self._toggle_repo.set_enabled(name, enabled)
        return self._view(name)

    async def run_now(self, name: str) -> JobRun:
        return await self._runner.trigger_now(name)

    def has_job(self, name: str) -> bool:
        return any(d.name == name for d in self._defs)

    def _view(self, name: str) -> ScheduledJobView:
        return next(v for v in self.list_jobs() if v.name == name)
