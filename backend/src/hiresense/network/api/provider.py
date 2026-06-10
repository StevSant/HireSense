from __future__ import annotations

from hiresense.network.domain import NetworkImportService
from hiresense.network.ports import ContactsRepositoryPort


class NetworkProvider:
    def __init__(
        self,
        import_service: NetworkImportService,
        repository: ContactsRepositoryPort,
    ) -> None:
        self._import_service = import_service
        self._repository = repository

    def get_import_service(self) -> NetworkImportService:
        return self._import_service

    def get_repository(self) -> ContactsRepositoryPort:
        return self._repository
