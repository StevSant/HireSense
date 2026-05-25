from __future__ import annotations

from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.apply_service import ApplyService
from hiresense.applications.domain.artifact_service import ArtifactService


class ApplicationsProvider:
    def __init__(
        self,
        application_service: ApplicationService,
        artifact_service: ArtifactService,
        apply_service: ApplyService,
    ) -> None:
        self._application_service = application_service
        self._artifact_service = artifact_service
        self._apply_service = apply_service

    def get_application_service(self) -> ApplicationService:
        return self._application_service

    def get_artifact_service(self) -> ArtifactService:
        return self._artifact_service

    def get_apply_service(self) -> ApplyService:
        return self._apply_service
