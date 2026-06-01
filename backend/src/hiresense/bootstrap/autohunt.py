from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.autohunt.api.provider import AutoHuntProvider
from hiresense.autohunt.domain import AutoHuntService
from hiresense.autohunt.infrastructure import DigestRepository
from hiresense.bootstrap.shared_infra import SharedInfra


@dataclass(frozen=True)
class AutoHuntBuild:
    provider: AutoHuntProvider
    service: AutoHuntService


def build_autohunt(
    infra: SharedInfra, jobs_repo: Any, pre_ranker: Any, profile_service: Any
) -> AutoHuntBuild:
    s = infra.settings
    service = AutoHuntService(
        jobs_repo=jobs_repo,
        pre_ranker=pre_ranker,
        profile_service=profile_service,
        digest_repo=DigestRepository(session_factory=infra.sync_session_factory),
        top_n=s.autohunt_top_n,
        min_score=s.autohunt_min_score,
        initial_lookback_days=s.autohunt_initial_lookback_days,
        retention_days=s.autohunt_digest_retention_days,
        language=s.default_language,
    )
    return AutoHuntBuild(provider=AutoHuntProvider(autohunt_service=service), service=service)
