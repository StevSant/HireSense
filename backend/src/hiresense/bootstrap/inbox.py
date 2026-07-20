from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.inbox.api.provider import InboxProvider
from hiresense.inbox.domain import (
    ApplicationMatcher,
    EmailClassifier,
    InboxProcessingService,
)
from hiresense.inbox.infrastructure import DetectedSignalRepositoryImpl, ImapInboxReader
from hiresense.tracking.domain.models import ApplicationStatus


@dataclass(frozen=True)
class InboxBuild:
    provider: InboxProvider
    service: InboxProcessingService


def build_inbox(
    infra: SharedInfra,
    tracked: Callable[[str], Any],
    *,
    tracking_service: Any,
    notification_service: Any = None,
) -> InboxBuild:
    s = infra.settings
    repo = DetectedSignalRepositoryImpl(session_factory=infra.sync_session_factory)
    reader = ImapInboxReader(
        host=s.imap_host,
        port=s.imap_port,
        username=s.imap_username,
        password=s.imap_password,
        folder=s.imap_folder,
        use_ssl=s.imap_use_ssl,
        timeout=s.imap_timeout,
        allow_insecure=s.imap_allow_insecure,
    )
    active = {ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEWING}

    def _list_active() -> list[Any]:
        apps: list[Any] = []
        for status in active:
            apps.extend(tracking_service.list(status=status))
        return apps

    service = InboxProcessingService(
        reader=reader,
        repo=repo,
        classifier=EmailClassifier(tracked("inbox-classification")),
        matcher=ApplicationMatcher(min_confidence=s.inbox_signal_match_min_confidence),
        list_active=_list_active,
        notifier=notification_service,
    )
    return InboxBuild(provider=InboxProvider(service=service, repo=repo), service=service)
