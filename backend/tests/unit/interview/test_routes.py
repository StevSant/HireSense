from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hiresense.identity.api.dependencies import require_auth
from hiresense.interview.api.dependencies import get_interview_prep_service, get_story_service
from hiresense.interview.api.routes import router
from hiresense.interview.domain.models import Competency, Story
from hiresense.interview.domain.services import InterviewPrep, StoryMatch


# ---------------------------------------------------------------------------
# Fake services
# ---------------------------------------------------------------------------


class FakeStoryService:
    def __init__(self) -> None:
        self._store: dict[uuid_mod.UUID, Story] = {}

    def _make_story(self, **kwargs) -> Story:
        story = Story(**kwargs)
        if story.id is None:
            story.id = uuid_mod.uuid4()
        now = datetime.now(timezone.utc)
        if story.created_at is None:
            story.created_at = now
        if story.updated_at is None:
            story.updated_at = now
        self._store[story.id] = story
        return story

    def add_story(
        self,
        title: str,
        competency: Competency,
        situation: str,
        task: str,
        action: str,
        result: str,
        reflection: str | None = None,
        tags: str | None = None,
    ) -> Story:
        return self._make_story(
            title=title,
            competency=competency.value,
            situation=situation,
            task=task,
            action=action,
            result=result,
            reflection=reflection,
            tags=tags,
        )

    def get(self, id: uuid_mod.UUID) -> Story:
        story = self._store.get(id)
        if story is None:
            raise ValueError(f"Story {id} not found")
        return story

    def list(self, competency: Competency | None = None) -> list[Story]:
        stories = list(self._store.values())
        if competency is not None:
            stories = [s for s in stories if s.competency == competency.value]
        return stories

    def update(self, id: uuid_mod.UUID, **fields) -> Story:
        story = self.get(id)
        for key, value in fields.items():
            setattr(story, key, value)
        story.updated_at = datetime.now(timezone.utc)
        return story

    def remove(self, id: uuid_mod.UUID) -> None:
        if id not in self._store:
            raise ValueError(f"Story {id} not found")
        del self._store[id]


class FakeInterviewPrepService:
    async def prepare(self, job: dict) -> InterviewPrep:
        return InterviewPrep(
            job_title=job.get("title", ""),
            company=job.get("company", ""),
            matched_stories=[],
            competencies_to_probe=["leadership", "communication"],
            technical_topics=["Python", "FastAPI"],
            negotiation_points=["Equity", "Remote work"],
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_app(fake_story: FakeStoryService, fake_prep: FakeInterviewPrepService) -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_story_service] = lambda: fake_story
    app.dependency_overrides[get_interview_prep_service] = lambda: fake_prep
    app.dependency_overrides[require_auth] = lambda: "test-user"
    app.include_router(router)
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_story() -> None:
    fake_story = FakeStoryService()
    fake_prep = FakeInterviewPrepService()
    client = TestClient(make_app(fake_story, fake_prep))

    resp = client.post(
        "/interview/stories",
        json={
            "title": "Led a team migration",
            "competency": "leadership",
            "situation": "Our team needed to migrate to a new system.",
            "task": "I was responsible for leading the migration.",
            "action": "I organized sprint planning and delegated tasks.",
            "result": "Migration completed two weeks ahead of schedule.",
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Led a team migration"
    assert data["competency"] == "leadership"
    assert "id" in data


def test_list_stories() -> None:
    fake_story = FakeStoryService()
    fake_prep = FakeInterviewPrepService()
    fake_story.add_story(
        title="Story A",
        competency=Competency.LEADERSHIP,
        situation="s",
        task="t",
        action="a",
        result="r",
    )
    fake_story.add_story(
        title="Story B",
        competency=Competency.COMMUNICATION,
        situation="s",
        task="t",
        action="a",
        result="r",
    )
    client = TestClient(make_app(fake_story, fake_prep))

    resp = client.get("/interview/stories")

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_story() -> None:
    fake_story = FakeStoryService()
    fake_prep = FakeInterviewPrepService()
    story = fake_story.add_story(
        title="Resolved conflict",
        competency=Competency.CONFLICT_RESOLUTION,
        situation="s",
        task="t",
        action="a",
        result="r",
    )
    client = TestClient(make_app(fake_story, fake_prep))

    resp = client.get(f"/interview/stories/{story.id}")

    assert resp.status_code == 200
    assert resp.json()["title"] == "Resolved conflict"


def test_get_story_not_found() -> None:
    fake_story = FakeStoryService()
    fake_prep = FakeInterviewPrepService()
    client = TestClient(make_app(fake_story, fake_prep))

    resp = client.get(f"/interview/stories/{uuid_mod.uuid4()}")

    assert resp.status_code == 404


def test_update_story() -> None:
    fake_story = FakeStoryService()
    fake_prep = FakeInterviewPrepService()
    story = fake_story.add_story(
        title="Old title",
        competency=Competency.TECHNICAL,
        situation="s",
        task="t",
        action="a",
        result="r",
    )
    client = TestClient(make_app(fake_story, fake_prep))

    resp = client.patch(
        f"/interview/stories/{story.id}",
        json={"title": "New title"},
    )

    assert resp.status_code == 200
    assert resp.json()["title"] == "New title"


def test_delete_story() -> None:
    fake_story = FakeStoryService()
    fake_prep = FakeInterviewPrepService()
    story = fake_story.add_story(
        title="To delete",
        competency=Competency.INITIATIVE,
        situation="s",
        task="t",
        action="a",
        result="r",
    )
    client = TestClient(make_app(fake_story, fake_prep))

    resp = client.delete(f"/interview/stories/{story.id}")

    assert resp.status_code == 204


def test_delete_story_not_found() -> None:
    fake_story = FakeStoryService()
    fake_prep = FakeInterviewPrepService()
    client = TestClient(make_app(fake_story, fake_prep))

    resp = client.delete(f"/interview/stories/{uuid_mod.uuid4()}")

    assert resp.status_code == 404


def test_prepare_interview() -> None:
    fake_story = FakeStoryService()
    fake_prep = FakeInterviewPrepService()
    client = TestClient(make_app(fake_story, fake_prep))

    resp = client.post(
        "/interview/prepare",
        json={
            "job_title": "Senior Backend Engineer",
            "company": "Acme Corp",
            "description": "We are looking for a backend engineer with Python experience.",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["job_title"] == "Senior Backend Engineer"
    assert data["company"] == "Acme Corp"
    assert "competencies_to_probe" in data
    assert "technical_topics" in data
    assert "negotiation_points" in data
