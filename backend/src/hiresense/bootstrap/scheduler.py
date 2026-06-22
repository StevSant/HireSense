from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.scheduler.api.provider import SchedulerProvider
from hiresense.scheduler.domain import JobDefinition, JobRunner
from hiresense.scheduler.infrastructure import (
    ApschedulerRunner,
    JobRunRepositoryImpl,
    JobToggleRepositoryImpl,
)


@dataclass(frozen=True)
class SchedulerBuild:
    provider: SchedulerProvider
    runner: ApschedulerRunner


def _digest_count(result: Any) -> int | None:
    return getattr(result, "job_count", None)


def build_scheduler(
    *,
    settings: Any,
    sync_session_factory: Any,
    ingestion_orchestrator: Any,
    revalidation_service: Any,
    autohunt_service: Any,
    outreach_service: Any,
) -> SchedulerBuild:
    definitions = [
        JobDefinition(
            name="ingestion_fetch",
            run=ingestion_orchestrator.run,
            cron=settings.ingestion_schedule,
            interval_hours=None,
            count_items=len,
        ),
        JobDefinition(
            name="revalidation_sweep",
            run=revalidation_service.sweep,
            cron=None,
            interval_hours=settings.job_revalidation_interval_hours,
            count_items=len,
        ),
        JobDefinition(
            name="autohunt_digest",
            run=autohunt_service.run,
            cron=settings.autohunt_schedule,
            interval_hours=None,
            count_items=_digest_count,
        ),
        JobDefinition(
            name="outreach_followups",
            # Compute-only: surfaces due nudges; never sends (Phase 5 gates send).
            run=_as_async(outreach_service.due_followups),
            cron=settings.outreach_followup_schedule,
            interval_hours=None,
            count_items=len,
        ),
    ]
    run_repo = JobRunRepositoryImpl(
        session_factory=sync_session_factory,
        retention_days=settings.scheduler_run_retention_days,
    )
    toggle_repo = JobToggleRepositoryImpl(session_factory=sync_session_factory)
    job_runner = JobRunner(definitions=definitions, run_repo=run_repo, toggle_repo=toggle_repo)
    runner = ApschedulerRunner(job_runner=job_runner, definitions=definitions)
    provider = SchedulerProvider(
        definitions=definitions, runner=runner, run_repo=run_repo, toggle_repo=toggle_repo
    )
    return SchedulerBuild(provider=provider, runner=runner)


def _as_async(sync_fn):
    """Adapt a sync callable (OutreachService.due_followups) to the async job
    signature the runner expects."""

    async def _wrapped():
        return sync_fn()

    return _wrapped
