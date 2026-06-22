from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.adapters import SmtpEmailSender
from hiresense.notifications.api.provider import NotificationProvider
from hiresense.notifications.domain import NotificationService


@dataclass(frozen=True)
class NotificationBuild:
    provider: NotificationProvider
    service: NotificationService


def build_notifications(settings: Any) -> NotificationBuild:
    sender = SmtpEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        from_email=settings.notification_from_email or settings.smtp_username,
        use_tls=settings.smtp_use_tls,
    )
    service = NotificationService(sender=sender, to_email=settings.notification_email)
    return NotificationBuild(provider=NotificationProvider(service), service=service)
