from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.outreach.api.provider import OutreachProvider
from hiresense.outreach.domain import OutreachMessageGenerator, OutreachService
from hiresense.outreach.infrastructure import OutreachRepository


@dataclass(frozen=True)
class OutreachBuild:
    provider: OutreachProvider
    service: OutreachService


def build_outreach(
    infra: SharedInfra,
    tracked: Any,
    tracking_service: Any,
    profile_service: Any,
    research_service: Any,
    *,
    portfolio_citation: Any = None,
) -> OutreachBuild:
    s = infra.settings
    service = OutreachService(
        tracking_service=tracking_service,
        profile_service=profile_service,
        research_service=research_service,
        generator=OutreachMessageGenerator(llm=tracked("outreach_message")),
        repo=OutreachRepository(session_factory=infra.sync_session_factory),
        style_guide_path=s.outreach_style_guide_path,
        followup_cadence_days=s.outreach_followup_cadence_days,
        max_chars=s.outreach_max_chars,
        language=s.default_language,
        portfolio_citation=portfolio_citation,
    )
    return OutreachBuild(provider=OutreachProvider(outreach_service=service), service=service)
