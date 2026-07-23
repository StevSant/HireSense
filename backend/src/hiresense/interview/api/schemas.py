from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateStoryRequest(BaseModel):
    title: str
    competency: str
    situation: str
    task: str
    action: str
    result: str
    reflection: str | None = None
    tags: str | None = None


class UpdateStoryRequest(BaseModel):
    title: str | None = None
    competency: str | None = None
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    reflection: str | None = None
    tags: str | None = None


class StoryResponse(BaseModel):
    id: uuid.UUID
    title: str
    competency: str
    situation: str
    task: str
    action: str
    result: str
    reflection: str | None
    tags: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PrepareRequest(BaseModel):
    job_title: str
    company: str
    description: str
    location: str | None = None
    interview_stage: str | None = None


class StoryMatchResponse(BaseModel):
    story_id: uuid.UUID
    story_title: str
    relevance: str


class InterviewPrepResponse(BaseModel):
    job_title: str
    company: str
    interview_stage: str | None
    matched_stories: list[StoryMatchResponse]
    competencies_to_probe: list[str]
    technical_topics: list[str]
    negotiation_points: list[str]
