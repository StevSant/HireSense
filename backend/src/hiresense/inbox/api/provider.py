from __future__ import annotations

from hiresense.inbox.domain import InboxProcessingService
from hiresense.inbox.domain.ports import DetectedSignalRepository


class InboxProvider:
    def __init__(self, *, service: InboxProcessingService, repo: DetectedSignalRepository) -> None:
        self._service = service
        self._repo = repo

    def get_service(self) -> InboxProcessingService:
        return self._service

    def get_repo(self) -> DetectedSignalRepository:
        return self._repo
