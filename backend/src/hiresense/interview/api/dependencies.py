from __future__ import annotations

from fastapi import Request

from hiresense.interview.domain import InterviewPrepService, StoryService


def get_story_service(request: Request) -> StoryService:
    return request.app.state.interview.get_story_service()


def get_interview_prep_service(request: Request) -> InterviewPrepService:
    return request.app.state.interview.get_interview_prep_service()
