from __future__ import annotations

from hiresense.tracking.domain import TrackingService


class TrackingProvider:
    def __init__(self, tracking_service: TrackingService) -> None:
        self._tracking_service = tracking_service

    def get_tracking_service(self) -> TrackingService:
        return self._tracking_service
