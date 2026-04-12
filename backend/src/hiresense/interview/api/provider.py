from __future__ import annotations

from hiresense.interview.domain import InterviewPrepService, StoryService


class InterviewProvider:
    def __init__(
        self,
        story_service: StoryService,
        interview_prep_service: InterviewPrepService,
    ) -> None:
        self._story_service = story_service
        self._interview_prep_service = interview_prep_service

    def get_story_service(self) -> StoryService:
        return self._story_service

    def get_interview_prep_service(self) -> InterviewPrepService:
        return self._interview_prep_service
