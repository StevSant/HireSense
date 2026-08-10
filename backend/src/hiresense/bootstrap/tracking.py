from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.tracking.api.provider import TrackingProvider
from hiresense.tracking.domain import TrackingService
from hiresense.tracking.infrastructure import TrackingRepository


@dataclass(frozen=True)
class TrackingBuild:
    provider: TrackingProvider
    service: TrackingService
    status_history_read: Any


def build_tracking(infra: SharedInfra, job_query: Any) -> TrackingBuild:
    tracking_repo = TrackingRepository(session_factory=infra.sync_session_factory)
    tracking_service = TrackingService(
        repository=tracking_repo,
        job_query=job_query,
        event_bus=infra.event_bus,
    )
    provider = TrackingProvider(tracking_service=tracking_service)
    return TrackingBuild(
        provider=provider, service=tracking_service, status_history_read=tracking_repo
    )
