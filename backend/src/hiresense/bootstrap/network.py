from __future__ import annotations

from dataclasses import dataclass

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.network.api.provider import NetworkProvider
from hiresense.network.domain import NetworkImportService
from hiresense.network.infrastructure import ContactsRepository


@dataclass(frozen=True)
class NetworkBuild:
    provider: NetworkProvider


def build_network(infra: SharedInfra) -> NetworkBuild:
    """Always built — the module is upload-driven, no external config."""
    repository = ContactsRepository(session_factory=infra.sync_session_factory)
    provider = NetworkProvider(
        import_service=NetworkImportService(repository=repository),
        repository=repository,
    )
    return NetworkBuild(provider=provider)
