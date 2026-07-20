from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hiresense.autopilot.api.provider import AutopilotProvider
from hiresense.autopilot.domain import AutopilotPipelineService
from hiresense.autopilot.infrastructure import DraftRepositoryImpl, ServicesApplicationDrafter
from hiresense.bootstrap.shared_infra import SharedInfra


@dataclass(frozen=True)
class AutopilotBuild:
    provider: AutopilotProvider
    service: AutopilotPipelineService


def build_autopilot(
    infra: SharedInfra,
    *,
    applications_provider: Any,
    latest_digest: Callable[[], Any],
    notification_service: Any = None,
) -> AutopilotBuild | None:
    s = infra.settings
    if not s.autopilot_pipeline_enabled:
        return None
    repo = DraftRepositoryImpl(session_factory=infra.sync_session_factory)
    drafter = ServicesApplicationDrafter(
        application_service=applications_provider.get_application_service(),
        artifact_service=applications_provider.get_artifact_service(),
        apply_service=applications_provider.get_apply_service(),
        cv_language=s.default_language,
    )
    service = AutopilotPipelineService(
        latest_digest=latest_digest,
        drafter=drafter,
        repo=repo,
        top_n=s.autopilot_pipeline_top_n,
        concurrency=s.autopilot_draft_concurrency,
        notifier=notification_service,
    )
    return AutopilotBuild(provider=AutopilotProvider(service=service, repo=repo), service=service)
