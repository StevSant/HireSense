from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from hiresense.interview.domain.models import Competency, Story


class StoryRepository:
    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def get_by_id(self, id: uuid.UUID) -> Story | None:
        with self._session_factory() as session:
            return session.get(Story, id)

    def list_all(self, competency: Competency | None = None) -> list[Story]:
        with self._session_factory() as session:
            stmt = select(Story)
            if competency is not None:
                stmt = stmt.where(Story.competency == competency.value)
            return list(session.scalars(stmt).all())

    def create(self, story: Story) -> Story:
        with self._session_factory() as session:
            session.add(story)
            session.commit()
            session.refresh(story)
            return story

    def save(self, story: Story) -> Story:
        with self._session_factory() as session:
            story = session.merge(story)
            session.commit()
            return story

    def delete(self, id: uuid.UUID) -> bool:
        with self._session_factory() as session:
            story = session.get(Story, id)
            if story is None:
                return False
            session.delete(story)
            session.commit()
            return True
