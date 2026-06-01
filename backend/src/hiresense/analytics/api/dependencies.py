from __future__ import annotations

from fastapi import Request

from hiresense.analytics.domain import AnalyticsService


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics.get_analytics_service()
