from hiresense.interview.domain.services import InterviewPrepService, StoryService


def get_story_service() -> StoryService:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")


def get_interview_prep_service() -> InterviewPrepService:
    raise NotImplementedError("Must be overridden during app startup via dependency_overrides")
