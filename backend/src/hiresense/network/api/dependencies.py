from __future__ import annotations

from fastapi import Request

from hiresense.network.domain import NetworkImportService
from hiresense.network.ports import ContactsRepositoryPort


def _provider(request: Request):
    return getattr(request.app.state, "network", None)


def get_import_service(request: Request) -> NetworkImportService | None:
    provider = _provider(request)
    return provider.get_import_service() if provider else None


def get_contacts_repository(request: Request) -> ContactsRepositoryPort | None:
    provider = _provider(request)
    return provider.get_repository() if provider else None
