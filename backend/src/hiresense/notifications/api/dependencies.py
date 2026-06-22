from __future__ import annotations

from fastapi import Request

from hiresense.notifications.domain import NotificationService


def get_notification_service(request: Request) -> NotificationService:
    return request.app.state.notifications.get_service()
