from __future__ import annotations

import uuid

from sqlalchemy import select

from hiresense.infrastructure import SqlRepository
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


class StoryRepository(SqlRepository):
    def get_by_id(self, id: uuid.UUID) -> Story | None:
        return self._get_by_pk(StoryOrm, id, _to_domain)

    def list_all(self, competency: Competency | None = None) -> list[Story]:
        stmt = select(StoryOrm)
        if competency is not None:
            stmt = stmt.where(StoryOrm.competency == competency.value)
        return self._select_all(stmt, _to_domain)

    def create(self, story: Story) -> Story:
        row = StoryOrm(**{field: getattr(story, field) for field in _CONTENT_FIELDS})
        return self._insert(row, _to_domain)

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
        return self._delete_by_pk(StoryOrm, id)
