from __future__ import annotations

from hiresense.analytics.domain import AnalyticsService


class AnalyticsProvider:
    def __init__(self, analytics_service: AnalyticsService) -> None:
        self._analytics_service = analytics_service

    def get_analytics_service(self) -> AnalyticsService:
        return self._analytics_service
