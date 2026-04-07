from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone

import pytest

from hiresense.interview.domain.models import Competency, Story
from hiresense.interview.domain.services import StoryService


class FakeRepository:
    def __init__(self) -> None:
        self._store: dict[uuid_mod.UUID, Story] = {}

    def create(self, story: Story) -> Story:
        if story.id is None:
            story.id = uuid_mod.uuid4()
        now = datetime.now(timezone.utc)
        if story.created_at is None:
            story.created_at = now
        if story.updated_at is None:
            story.updated_at = now
        self._store[story.id] = story
        return story

    def get_by_id(self, id: uuid_mod.UUID) -> Story | None:
        return self._store.get(id)

    def list_all(self, competency: Competency | None = None) -> list[Story]:
        stories = list(self._store.values())
        if competency is not None:
            stories = [s for s in stories if s.competency == competency.value]
        return stories

    def save(self, story: Story) -> Story:
        story.updated_at = datetime.now(timezone.utc)
        self._store[story.id] = story
        return story

    def delete(self, id: uuid_mod.UUID) -> bool:
        if id in self._store:
            del self._store[id]
            return True
        return False


def make_service(repo: FakeRepository | None = None) -> StoryService:
    return StoryService(repository=repo or FakeRepository())


def test_add_story() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)

    story = svc.add_story(
        title="Delivered under pressure",
        competency=Competency.ADAPTABILITY,
        situation="Requirements changed mid-sprint",
        task="Reprioritize and deliver core features",
        action="Held quick planning session, dropped low-priority items",
        result="Delivered MVP on time",
    )

    assert story.id is not None
    assert story.title == "Delivered under pressure"
    assert story.competency == Competency.ADAPTABILITY.value
    assert story.reflection is None
    assert story.tags is None


def test_add_story_with_optional_fields() -> None:
    svc = make_service()

    story = svc.add_story(
        title="Shipped new feature",
        competency=Competency.TECHNICAL,
        situation="Legacy codebase with no tests",
        task="Add feature safely",
        action="Added tests first, then implemented",
        result="Zero regressions",
        reflection="TDD is powerful",
        tags="backend,python",
    )

    assert story.reflection == "TDD is powerful"
    assert story.tags == "backend,python"


def test_get_story() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    created = svc.add_story(
        title="Collaborated on design",
        competency=Competency.COLLABORATION,
        situation="Cross-team project",
        task="Align APIs between teams",
        action="Weekly syncs, shared design doc",
        result="Smooth integration",
    )

    fetched = svc.get(created.id)

    assert fetched.id == created.id
    assert fetched.title == "Collaborated on design"


def test_get_story_not_found() -> None:
    svc = make_service()
    with pytest.raises(ValueError, match="not found"):
        svc.get(uuid_mod.uuid4())


def test_list_stories() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    svc.add_story(
        title="A", competency=Competency.LEADERSHIP,
        situation="s", task="t", action="a", result="r",
    )
    svc.add_story(
        title="B", competency=Competency.TECHNICAL,
        situation="s", task="t", action="a", result="r",
    )

    stories = svc.list()

    assert len(stories) == 2


def test_list_stories_filter_by_competency() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    svc.add_story(
        title="A", competency=Competency.LEADERSHIP,
        situation="s", task="t", action="a", result="r",
    )
    svc.add_story(
        title="B", competency=Competency.TECHNICAL,
        situation="s", task="t", action="a", result="r",
    )

    results = svc.list(competency=Competency.TECHNICAL)

    assert len(results) == 1
    assert results[0].title == "B"


def test_update_story() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    story = svc.add_story(
        title="Original",
        competency=Competency.COMMUNICATION,
        situation="s", task="t", action="a", result="r",
    )

    updated = svc.update(story.id, title="Updated", reflection="Learned a lot")

    assert updated.title == "Updated"
    assert updated.reflection == "Learned a lot"


def test_update_story_not_found() -> None:
    svc = make_service()
    with pytest.raises(ValueError, match="not found"):
        svc.update(uuid_mod.uuid4(), title="Ghost")


def test_remove_story() -> None:
    repo = FakeRepository()
    svc = make_service(repo=repo)
    story = svc.add_story(
        title="To be removed",
        competency=Competency.INITIATIVE,
        situation="s", task="t", action="a", result="r",
    )

    svc.remove(story.id)

    with pytest.raises(ValueError, match="not found"):
        svc.get(story.id)


def test_remove_story_not_found() -> None:
    svc = make_service()
    with pytest.raises(ValueError, match="not found"):
        svc.remove(uuid_mod.uuid4())
