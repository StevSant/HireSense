from __future__ import annotations

from fastapi import Depends, Request

from hiresense.applications.api.provider import ApplicationsProvider
from hiresense.applications.domain.application_service import ApplicationService
from hiresense.applications.domain.apply_service import ApplyService
from hiresense.applications.domain.artifact_service import ArtifactService


def _get_provider(request: Request) -> ApplicationsProvider:
    provider = getattr(request.app.state, "applications_provider", None)
    if provider is None:
        raise RuntimeError("applications_provider not configured in app.state")
    return provider


def get_application_service(
    provider: ApplicationsProvider = Depends(_get_provider),
) -> ApplicationService:
    return provider.get_application_service()


def get_artifact_service(
    provider: ApplicationsProvider = Depends(_get_provider),
) -> ArtifactService:
    return provider.get_artifact_service()


def get_apply_service(
    provider: ApplicationsProvider = Depends(_get_provider),
) -> ApplyService:
    return provider.get_apply_service()
