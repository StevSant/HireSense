from __future__ import annotations

from dataclasses import dataclass

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.preference.api.provider import PreferenceProvider
from hiresense.preference.domain import (
    FeedbackKind,
    PreferenceService,
    TasteVectorCalculator,
)
from hiresense.preference.infrastructure import PreferenceRepository


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
    return PreferenceBuild(provider=PreferenceProvider(preference_service=service), service=service)
