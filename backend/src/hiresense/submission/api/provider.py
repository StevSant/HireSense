from __future__ import annotations

from typing import Any

from hiresense.submission.domain import SubmissionService
from hiresense.submission.domain.ports import SubmissionRepository


class SubmissionProvider:
    def __init__(
        self,
        *,
        service: SubmissionService,
        repo: SubmissionRepository,
        context_builder: Any = None,
    ) -> None:
        self._service = service
        self._repo = repo
        self._context_builder = context_builder

    def get_service(self) -> SubmissionService:
        return self._service

    def get_repo(self) -> SubmissionRepository:
        return self._repo

    def get_context_builder(self) -> Any:
        return self._context_builder
