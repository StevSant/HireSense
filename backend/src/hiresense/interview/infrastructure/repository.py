from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.interview.domain.models import Competency, Story
from hiresense.interview.infrastructure.orm import StoryOrm

_CONTENT_FIELDS = (
    "title",
    "competency",
    "situation",
    "task",
    "action",
    "result",
    "reflection",
    "tags",
)


def _to_domain(row: StoryOrm) -> Story:
    return Story.model_validate(row)


class StoryRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_id(self, id: uuid.UUID) -> Story | None:
        with self._session_factory() as session:
            row = session.get(StoryOrm, id)
            return _to_domain(row) if row is not None else None

    def list_all(self, competency: Competency | None = None) -> list[Story]:
        with self._session_factory() as session:
            stmt = select(StoryOrm)
            if competency is not None:
                stmt = stmt.where(StoryOrm.competency == competency.value)
            return [_to_domain(r) for r in session.scalars(stmt).all()]

    def create(self, story: Story) -> Story:
        with self._session_factory() as session:
            row = StoryOrm(**{field: getattr(story, field) for field in _CONTENT_FIELDS})
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def save(self, story: Story) -> Story:
        with self._session_factory() as session:
            row = session.get(StoryOrm, story.id) if story.id else None
            if row is None:
                row = StoryOrm(**{field: getattr(story, field) for field in _CONTENT_FIELDS})
                session.add(row)
            else:
                for field in _CONTENT_FIELDS:
                    setattr(row, field, getattr(story, field))
            session.commit()
            session.refresh(row)
            return _to_domain(row)

    def delete(self, id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            row = session.get(StoryOrm, id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
