from __future__ import annotations

from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.apply_service import ApplyService
from hiresense.applications.domain.artifact_service import ArtifactService
from hiresense.applications.domain.application_packet import ApplicationPacketService
from hiresense.applications.ports import ApplicationRepositoryPort


class ApplicationsProvider:
    def __init__(
        self,
        application_service: ApplicationService,
        artifact_service: ArtifactService,
        apply_service: ApplyService,
        packet_service: ApplicationPacketService,
        repository: ApplicationRepositoryPort | None = None,
    ) -> None:
        self._application_service = application_service
        self._artifact_service = artifact_service
        self._apply_service = apply_service
        self._packet_service = packet_service
        self._repository = repository

    def get_application_service(self) -> ApplicationService:
        return self._application_service

    def get_artifact_service(self) -> ArtifactService:
        return self._artifact_service

    def get_apply_service(self) -> ApplyService:
        return self._apply_service

    def get_packet_service(self) -> ApplicationPacketService:
        return self._packet_service

    def get_repository(self) -> ApplicationRepositoryPort | None:
        """The shared application repository.

        Exposed so sibling modules can read job snapshots and match rows
        without reaching into a service's private attributes.
        """
        return self._repository
