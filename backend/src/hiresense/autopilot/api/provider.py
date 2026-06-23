from __future__ import annotations

from hiresense.autopilot.domain import AutopilotPipelineService
from hiresense.autopilot.domain.ports import DraftRepository


class AutopilotProvider:
    def __init__(self, *, service: AutopilotPipelineService, repo: DraftRepository) -> None:
        self._service = service
        self._repo = repo

    def get_service(self) -> AutopilotPipelineService:
        return self._service

    def get_repo(self) -> DraftRepository:
        return self._repo
