from __future__ import annotations

from fastapi import Request

from hiresense.tracking.domain import TrackingService


def get_tracking_service(request: Request) -> TrackingService:
    return request.app.state.tracking.get_tracking_service()
