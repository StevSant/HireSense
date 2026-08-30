from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hiresense.autopilot.api.provider import AutopilotProvider
from hiresense.autopilot.domain import AutopilotPipelineService
from hiresense.autopilot.infrastructure import (
    DraftRepositoryImpl,
    PacketApprovingEnqueuer,
    ServicesApplicationDrafter,
)
from hiresense.composition.shared_infra import SharedInfra


@dataclass(frozen=True)
class AutopilotBuild:
    provider: AutopilotProvider
    service: AutopilotPipelineService


def build_autopilot(
    infra: SharedInfra,
    *,
    applications_provider: Any,
    latest_digest: Callable[[], Any],
    job_query: Any | None = None,
    notification_service: Any = None,
    submission_service: Any = None,
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
    # Phase 5: only build the enqueuer when the outbound queue exists. With
    # auto-apply disabled `submission_service` is None and the pipeline stops
    # at drafting, exactly as it did before.
    enqueuer = None
    if submission_service is not None:
        enqueuer = PacketApprovingEnqueuer(
            applications_provider.get_packet_service(),
            submission_service,
            applications_provider.get_repository(),
            min_score=s.autopilot_submit_min_score,
        )

    service = AutopilotPipelineService(
        latest_digest=latest_digest,
        drafter=drafter,
        repo=repo,
        job_query=job_query,
        top_n=s.autopilot_pipeline_top_n,
        concurrency=s.autopilot_draft_concurrency,
        notifier=notification_service,
        submission_enqueuer=enqueuer,
    )
    return AutopilotBuild(provider=AutopilotProvider(service=service, repo=repo), service=service)
