from __future__ import annotations

from fastapi import Request

from hiresense.scheduler.api.provider import SchedulerProvider


def get_scheduler_provider(request: Request) -> SchedulerProvider:
    return request.app.state.scheduler
