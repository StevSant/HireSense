from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hiresense.bootstrap.shared_infra import SharedInfra
from hiresense.interview.api.provider import InterviewProvider
from hiresense.interview.domain import InterviewPrepService, StoryService
from hiresense.interview.infrastructure import StoryRepository


@dataclass(frozen=True)
class InterviewBuild:
    provider: InterviewProvider
    prep_service: InterviewPrepService


def build_interview(infra: SharedInfra, tracked: Callable[[str], Any]) -> InterviewBuild:
    story_repo = StoryRepository(session_factory=infra.sync_session_factory)
    story_service = StoryService(repository=story_repo)
    interview_prep_service = InterviewPrepService(
        llm=tracked("interview_prep"),
        story_repo=story_repo,
    )
    provider = InterviewProvider(
        story_service=story_service,
        interview_prep_service=interview_prep_service,
    )
    return InterviewBuild(provider=provider, prep_service=interview_prep_service)
