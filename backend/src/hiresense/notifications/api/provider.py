from __future__ import annotations

from hiresense.notifications.domain import NotificationService


class NotificationProvider:
    def __init__(self, service: NotificationService) -> None:
        self._service = service

    def get_service(self) -> NotificationService:
        return self._service
