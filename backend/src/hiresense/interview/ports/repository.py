from __future__ import annotations

import uuid
from typing import Protocol

from hiresense.interview.domain.models import Competency, Story


class StoryRepositoryPort(Protocol):
    def get_by_id(self, id: uuid.UUID) -> Story | None: ...

    def list_all(self, competency: Competency | None = None) -> list[Story]: ...

    def create(self, story: Story) -> Story: ...

    def save(self, story: Story) -> Story: ...

    def delete(self, id: uuid.UUID) -> bool: ...
