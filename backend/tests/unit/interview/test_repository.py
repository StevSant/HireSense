from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hiresense.infrastructure.database import Base
from hiresense.interview.domain.models import Competency, Story
from hiresense.interview.infrastructure import StoryOrm, StoryRepository


@pytest.fixture
def sync_session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    Base.metadata.drop_all(engine)


@pytest.fixture
def repo(sync_session_factory):
    return StoryRepository(session_factory=sync_session_factory)


def _story(**kwargs) -> Story:
    defaults = dict(
        title="Resolved a conflict",
        competency=Competency.CONFLICT_RESOLUTION.value,
        situation="Two team members disagreed",
        task="Mediate and find common ground",
        action="Facilitated a structured conversation",
        result="Agreement reached within one hour",
    )
    defaults.update(kwargs)
    return Story(**defaults)


def _seed(session_factory, **kwargs) -> uuid.UUID:
    """Insert a row directly via the ORM and return its id."""
    story = _story(**kwargs)
    with session_factory() as session:
        row = StoryOrm(**story.model_dump(exclude={"id", "created_at", "updated_at"}))
        session.add(row)
        session.commit()
        return row.id


def test_create_and_get_by_id(repo, sync_session_factory) -> None:
    created_id = _seed(sync_session_factory, title="Led a team")
    result = repo.get_by_id(created_id)
    assert result is not None
    assert result.title == "Led a team"


def test_get_by_id_not_found(repo) -> None:
    result = repo.get_by_id(uuid.uuid4())
    assert result is None


def test_create_via_repo(repo) -> None:
    created = repo.create(_story(title="Mentored juniors", competency=Competency.LEADERSHIP.value))
    assert created.id is not None
    assert created.title == "Mentored juniors"


def test_list_all(repo, sync_session_factory) -> None:
    _seed(sync_session_factory, title="A", competency=Competency.LEADERSHIP.value)
    _seed(sync_session_factory, title="B", competency=Competency.TECHNICAL.value)
    results = repo.list_all()
    assert len(results) == 2


def test_list_all_filter_by_competency(repo, sync_session_factory) -> None:
    _seed(sync_session_factory, title="A", competency=Competency.LEADERSHIP.value)
    _seed(sync_session_factory, title="B", competency=Competency.TECHNICAL.value)
    results = repo.list_all(competency=Competency.TECHNICAL)
    assert len(results) == 1
    assert results[0].title == "B"


def test_save(repo, sync_session_factory) -> None:
    story_id = _seed(sync_session_factory, title="Original title")
    fetched = repo.get_by_id(story_id)
    fetched.title = "Updated title"
    repo.save(fetched)
    result = repo.get_by_id(story_id)
    assert result.title == "Updated title"


def test_delete(repo, sync_session_factory) -> None:
    story_id = _seed(sync_session_factory)
    deleted = repo.delete(story_id)
    assert deleted is True
    assert repo.get_by_id(story_id) is None


def test_delete_not_found(repo) -> None:
    deleted = repo.delete(uuid.uuid4())
    assert deleted is False
