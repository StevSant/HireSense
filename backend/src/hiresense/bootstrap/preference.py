from __future__ import annotations

import logging
import uuid as uuid_mod
from dataclasses import dataclass

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.kernel.events import TrackingStatusChangedEvent
from hiresense.preference.api.provider import PreferenceProvider
from hiresense.preference.domain import (
    FeedbackKind,
    PreferenceService,
    TasteVectorCalculator,
    status_to_feedback_kind,
)
from hiresense.preference.infrastructure import PreferenceRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreferenceBuild:
    provider: PreferenceProvider
    service: PreferenceService


def build_preference(infra: SharedInfra) -> PreferenceBuild:
    s = infra.settings
    calculator = TasteVectorCalculator(
        alpha=s.preference_alpha,
        beta=s.preference_beta,
        gamma=s.preference_gamma,
        tau_days=s.preference_decay_tau_days,
    )
    weights = {kind: float(getattr(s, kind.weight_key)) for kind in FeedbackKind}
    service = PreferenceService(
        repository=PreferenceRepository(session_factory=infra.sync_session_factory),
        vector_store=infra.vector_store,
        calculator=calculator,
        weights=weights,
        enabled=s.preference_enabled,
    )
    async def _on_status_changed(event: TrackingStatusChangedEvent) -> None:
        kind = status_to_feedback_kind(event.status)
        if kind is None or event.job_id is None:
            return
        # The in-memory bus already isolates handler failures (see
        # InMemoryEventBus._safe_invoke), so this guard mainly adds job-id
        # context to the log and stays resilient if the bus is ever swapped.
        try:
            await service.record_implicit_signal(uuid_mod.UUID(event.job_id), kind)
        except Exception:
            logger.exception("preference: implicit signal failed for job %s", event.job_id)

    infra.event_bus.subscribe("tracking.status_changed", _on_status_changed)

    return PreferenceBuild(provider=PreferenceProvider(preference_service=service), service=service)
