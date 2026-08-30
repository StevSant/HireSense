from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hiresense.composition.shared_infra import SharedInfra
from hiresense.shared.ports import LLMPort
from hiresense.submission.api.provider import SubmissionProvider
from hiresense.submission.domain import FormAgentService, SubmissionService
from hiresense.submission.infrastructure import (
    AttemptContextBuilder,
    LLMFormAnswerer,
    ProfileAnswerBank,
    SubmissionRepositoryImpl,
)

# Feature key the tracked-LLM factory bills auto-apply form answering against,
# so its spend shows up in admin usage tracking like every other feature.
FORM_ANSWER_FEATURE = "submission_form_answer"


@dataclass(frozen=True)
class SubmissionBuild:
    provider: SubmissionProvider
    service: SubmissionService


def build_submission(
    infra: SharedInfra,
    tracked: Callable[[str], LLMPort | None],
    *,
    profile_service: Any,
    claim_service: Any = None,
    job_query: Any = None,
    notification_service: Any = None,
) -> SubmissionBuild | None:
    """Wire the auto-apply submission queue, or nothing when it is disabled.

    Returns None unless `autopilot_submit_enabled` is set, so a default install
    exposes no outbound routes at all -- the safest possible default for a
    subsystem that submits applications under the user's name.
    """
    s = infra.settings
    if not s.autopilot_submit_enabled:
        return None

    repo = SubmissionRepositoryImpl(session_factory=infra.sync_session_factory)
    llm = tracked(FORM_ANSWER_FEATURE)
    agent = FormAgentService(
        LLMFormAnswerer(llm) if llm is not None else _NullAnswerer(),
        confidence_threshold=s.submission_confidence_threshold,
        dry_run=s.apply_agent_dry_run,
    )
    service = SubmissionService(
        repo,
        agent,
        ProfileAnswerBank(profile_service),
        daily_cap=s.autopilot_submit_daily_cap,
        lease_seconds=s.submission_lease_seconds,
        max_attempts=s.submission_max_attempts,
        notifier=notification_service,
    )
    context_builder = AttemptContextBuilder(
        profile_service=profile_service,
        claim_service=claim_service,
        job_query=job_query,
    )
    provider = SubmissionProvider(service=service, repo=repo, context_builder=context_builder)
    return SubmissionBuild(provider=provider, service=service)


class _NullAnswerer:
    """Stands in when no LLM is configured (APP_MODE=local with a blank key).

    Returns no answers, so every non-deterministic field escalates to the human
    instead of the agent guessing. Degrading toward the review queue is the
    correct direction for this subsystem.
    """

    async def answer(self, **_kwargs: Any) -> list[Any]:
        return []
