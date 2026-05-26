from __future__ import annotations

import uuid
from typing import Any, Protocol

from hiresense.profile.domain.models import Profile


class ProfileRepositoryPort(Protocol):
    def get_by_id(self, id: uuid.UUID) -> Profile | None: ...

    def get_latest(self, language: str | None = None) -> Profile | None: ...

    def list_all(self) -> list[Profile]: ...

    def create(self, profile: Profile) -> Profile: ...

    def update(self, id: uuid.UUID, fields: dict[str, Any]) -> Profile | None: ...

    def update_all(self, fields: dict[str, Any]) -> int: ...
